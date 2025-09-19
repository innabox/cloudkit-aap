# pyright: reportExplicitAny=false

import json
import subprocess
import yaml

from typing import Any
from typing import cast
from typing import Literal
from typing import Self
from typing import TypedDict

from collections.abc import Generator

from pathlib import Path
from enum import StrEnum

import pydantic

AnsibleArgumentType = Literal[
    "str",
    "string",
    "list",
    "dict",
    "bool",
    "int",
    "float",
    "path",
    "raw",
    "json",
    "jsonarg",
    "bytes",
    "bits",
]


# Type hint for TemplateParameter.from_argspec method
class AnsibleArgumentSpecEntry(TypedDict):
    name: str
    short_description: str | None
    description: str | None
    type: AnsibleArgumentType
    required: bool
    default: Any
    choices: list[Any]
    options: dict[str, "AnsibleArgumentSpecEntry"]  # Recursive definition


# Type hint for reading argument_specs.yaml files
class AnsibleArgumentSpec(TypedDict):
    argument_specs: dict[str, AnsibleArgumentSpecEntry]


# Type hint for the output of `ansible-galaxy collection list`
AnsibleCollectionList = dict[str, dict[str, dict[str, str]]]


class ProtobufType(StrEnum):
    BOOL = "type.googleapis.com/google.protobuf.BoolValue"
    INT = "type.googleapis.com/google.protobuf.Int64Value"
    FLOAT = "type.googleapis.com/google.protobuf.DoubleValue"
    STRING = "type.googleapis.com/google.protobuf.StringValue"
    BYTEARRAY = "type.googleapis.com/google.protobuf.BytesValue"
    ANY = "type.googleapis.com/google.protobuf.Value"


# This maps Ansible argument types [1] and Python types to the protobuf types
# [2] used in the fulfillment service.
#
# [1]: https://docs.ansible.com/ansible/latest/dev_guide/developing_program_flow_modules.html#argument-spec
# [2]: https://googleapis.dev/nodejs/analytics-admin/latest/google.protobuf.html
TypeMapping: dict[AnsibleArgumentType | type, ProtobufType] = {
    "str": ProtobufType.STRING,
    str: ProtobufType.STRING,
    "list": ProtobufType.ANY,
    "dict": ProtobufType.ANY,
    "bool": ProtobufType.BOOL,
    bool: ProtobufType.BOOL,
    "int": ProtobufType.INT,
    int: ProtobufType.INT,
    "float": ProtobufType.FLOAT,
    float: ProtobufType.FLOAT,
    "path": ProtobufType.STRING,
    "json": ProtobufType.STRING,
    "bytes": ProtobufType.BYTEARRAY,
}


class Base(pydantic.BaseModel):
    pass


class ProtobufAnyValue(Base):
    type: ProtobufType = pydantic.Field(
        ProtobufType.STRING, serialization_alias="@type"
    )
    value: Any


class TemplateParameter(Base):
    """TemplateParameter represents a single template paramter"""

    name: str
    title: str | None
    description: str | None
    required: bool = False
    type: ProtobufType = ProtobufType.STRING
    default: ProtobufAnyValue | None = None
    choices: list[Any] | None = None

    @classmethod
    def from_argspec(cls, name: str, spec: AnsibleArgumentSpecEntry) -> Self:
        """Given an option name and Ansible argument spec, return a TemplateParameter"""
        return cls(
            name=name,
            title=spec.get("short_description"),
            description=spec.get("description"),
            default=spec.get("default"),
            type=TypeMapping[spec.get("type", "str")],
        )

    @pydantic.field_validator("default", mode="before")
    @classmethod
    def validate_default(cls, value: Any) -> ProtobufAnyValue | None:
        """The 'default' field in the fulfillment API is using the `protobufAny` schema
        defined in [1]. This requires a value of the form:

            {
                "@type": "type.googleapis.com/google.protobuf.StringValue",
                "value": "my default value"
            }

        We handle this with a "before" field validator which transforms a
        Python variable into a ProtobufAnyValue object by mapping the variable
        type to the protobuf type string via the `TypeMapping` table, and then
        storing the actual value in the "value" key.

        Note that we only handle scalar values; an attempt to use something
        other than a string, bool, float, or int will result in a validation
        error.

        [1]: https://raw.githubusercontent.com/innabox/fulfillment-api/refs/heads/main/openapi/v3/openapi.yaml
        """
        if value is not None:
            try:
                return ProtobufAnyValue(type=TypeMapping[type(value)], value=value)
            except KeyError as err:
                raise ValueError(f"Default values must be scalar type, not {err}")


class NodeRequest(Base):
    """NodeRequest represents the bare metal resources requested for a cluster"""

    resource_class: str = pydantic.Field(..., validation_alias="resourceClass")
    number_of_nodes: int = pydantic.Field(..., validation_alias="numberOfNodes")


class Metadata(Base):
    """Metadata about the template"""

    title: str
    description: str | None = None
    template_type: str | None = None  # "cluster" or "vm"
    default_node_request: list[NodeRequest]
    allowed_resource_classes: list[str] | None = None


class Template(Base):
    """Role represents a single template role"""

    collection: str = pydantic.Field(..., exclude=True)
    path: Path = pydantic.Field(..., exclude=True)

    name: str = pydantic.Field(..., exclude=True)
    title: str | None = None
    description: str | None = None
    template_type: str | None = pydantic.Field(None, exclude=True)  # "cluster" or "vm"

    # Not currently supported by the API
    default_node_request: list[NodeRequest] = pydantic.Field(..., exclude=True)
    allowed_resource_classes: list[str] | None = pydantic.Field(None, exclude=True)

    parameters: list[TemplateParameter]

    @pydantic.field_serializer("path")
    def serialize_path(self, value: Path):
        return str(value)

    @pydantic.computed_field
    def id(self) -> str:
        return f"{self.collection}.{self.name}"


class Collection(Base):
    """Collection represents an Ansible collection"""

    parent_path: Path
    name: str

    def read_metadata_for_role(self, path: Path) -> Metadata | None:
        for filename in ["cloudkit.yaml", "cloudkit.yml"]:
            metadata_file: Path = path / "meta" / filename
            if metadata_file.exists():
                break
        else:
            return

        with metadata_file.open("r") as fd:
            metadata = yaml.safe_load(fd)

        if metadata:
            return Metadata.model_validate(metadata)

    def read_params_for_role(self, path: Path) -> list[TemplateParameter]:
        for filename in ["argument_specs.yaml", "argument_specs.yml"]:
            argspec_file = path / "meta" / filename
            if argspec_file.exists():
                break
        else:
            return []

        with argspec_file.open("r") as fd:
            argspec: AnsibleArgumentSpec = cast(AnsibleArgumentSpec, yaml.safe_load(fd))

        template_params: list[TemplateParameter] = []

        for name, spec in (
            argspec.get("argument_specs", {})
            .get("main", {})
            .get("options", {})
            .get("template_parameters", {})
            .get("options", {})
            .items()
        ):
            template_params.append(TemplateParameter.from_argspec(name, spec))

        return template_params

    def templates(self):
        for path in (self.parent_path / self.name.replace(".", "/") / "roles").glob(
            "*"
        ):
            metadata = self.read_metadata_for_role(path)
            params = self.read_params_for_role(path)
            if metadata is not None:
                template = Template(
                    collection=self.name,
                    path=path,
                    name=path.name,
                    title=metadata.title,
                    description=metadata.description,
                    template_type=metadata.template_type,
                    default_node_request=metadata.default_node_request,
                    allowed_resource_classes=metadata.allowed_resource_classes,
                    parameters=params,
                )
                yield template


def find_template_roles(requested: list[str]) -> Generator[Template, None, None]:
    collections: list[Collection] = []
    for collection in requested:
        info: AnsibleCollectionList = cast(
            AnsibleCollectionList,
            json.loads(
                subprocess.check_output(
                    [
                        "ansible-galaxy",
                        "collection",
                        "list",
                        collection,
                        "--format",
                        "json",
                    ],
                    stderr=subprocess.DEVNULL,
                )
            ),
        )

        if info:
            # If `ansible-galaxy collection list` find multiple collections with the given name,
            # we will select the first one.
            collections.append(
                Collection(parent_path=Path(list(info.keys())[0]), name=collection)
            )

    for collection in collections:
        yield from collection.templates()


def find_template_roles_filter(requested: list[str]):
    """Transform the return values from find_template_roles into something
    that makes Ansible happy."""
    return [
        role.model_dump(by_alias=True, exclude_none=True)
        for role in find_template_roles(requested)
    ]


def find_cluster_template_roles_filter(requested: list[str]):
    """Transform the return values from find_template_roles into something
    that makes Ansible happy, but only for cluster templates."""
    return [
        role.model_dump(by_alias=True, exclude_none=True)
        for role in find_template_roles(requested)
        if role.template_type == "cluster" or role.template_type is None  # Default to cluster for backward compatibility
    ]


def find_vm_template_roles_filter(requested: list[str]):
    """Transform the return values from find_template_roles into something
    that makes Ansible happy, but only for VM templates."""
    return [
        role.model_dump(by_alias=True, exclude_none=True)
        for role in find_template_roles(requested)
        if role.template_type == "vm"
    ]


class FilterModule:
    def filters(self):
        return {
            "find_template_roles": find_template_roles_filter,
            "find_cluster_template_roles": find_cluster_template_roles_filter,
            "find_vm_template_roles": find_vm_template_roles_filter,
        }


if __name__ == "__main__":
    import sys

    found = find_template_roles_filter(sys.argv[1:])
    print(json.dumps(list(found)))
