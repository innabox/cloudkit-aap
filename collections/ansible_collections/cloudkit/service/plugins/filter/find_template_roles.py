# pyright: reportExplicitAny=false

import json
import re
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

from ansible.utils.display import Display
from ansible.errors import AnsibleFilterError

display = Display()

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
    """Base model with common Pydantic configuration for all models."""

    model_config = pydantic.ConfigDict(
        # Keep flexible for Ansible data (YAML can have various formats)
        strict=False,
        # Validate on assignment for better error detection
        validate_assignment=True,
        # Allow arbitrary types (needed for Path objects)
        arbitrary_types_allowed=True,
    )


class ProtobufAnyValue(Base):
    type: ProtobufType = pydantic.Field(
        ProtobufType.STRING, serialization_alias="@type"
    )
    value: Any


class TemplateParameter(Base):
    """TemplateParameter represents a single template parameter"""

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
            required=spec.get("required", False),
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
                raise ValueError(
                    f"Default values must be scalar type, not {err}")


class NodeRequest(Base):
    """NodeRequest represents the bare metal resources requested for a cluster"""

    resource_class: str = pydantic.Field(..., validation_alias="resourceClass")
    number_of_nodes: int = pydantic.Field(...,
                                          validation_alias="numberOfNodes")


class NodeSet(Base):
    """NodeSet represents the template's default bare metal resources"""

    host_class: str
    size: int


class TemplateTypeEnum(StrEnum):
    cluster = "cluster"
    compute_instance = "compute_instance"


class Metadata(Base):
    """Metadata about the template"""

    title: str
    description: str | None = None
    template_type: TemplateTypeEnum = pydantic.Field(
        default=TemplateTypeEnum.cluster, exclude=True
    )
    default_node_request: list[NodeRequest] = pydantic.Field(default_factory=list)
    allowed_resource_classes: list[str] | None = None


class BaseTemplate(Base):
    """Base class for all template types"""

    collection: str = pydantic.Field(..., exclude=True)
    path: Path = pydantic.Field(..., exclude=True)
    name: str = pydantic.Field(..., exclude=True)
    title: str | None = None
    description: str | None = None
    template_type: TemplateTypeEnum = pydantic.Field(exclude=True)
    parameters: list[TemplateParameter]

    @pydantic.field_serializer("path")
    def serialize_path(self, value: Path):
        return str(value)

    @pydantic.computed_field
    def id(self) -> str:
        return f"{self.collection}.{self.name}"


class ClusterTemplate(BaseTemplate):
    """Template for cluster deployments"""

    template_type: Literal[TemplateTypeEnum.cluster] = TemplateTypeEnum.cluster
    default_node_request: list[NodeRequest] = pydantic.Field(default=[], exclude=True)
    allowed_resource_classes: list[str] | None = pydantic.Field(None, exclude=True)

    @pydantic.computed_field
    def node_sets(self) -> dict[str, NodeSet] | None:
        ret = {
            nr.resource_class: NodeSet(
                host_class=nr.resource_class, size=nr.number_of_nodes
            )
            for nr in self.default_node_request
        }
        return ret if ret else None


class ComputeInstanceTemplate(BaseTemplate):
    """Template for ComputeInstance deployments"""

    template_type: Literal[TemplateTypeEnum.compute_instance] = TemplateTypeEnum.compute_instance

def _validate_collection_name(name: str) -> None:
    """Validate that collection name follows namespace.collection format.

    Args:
        name: Collection name to validate

    Raises:
        AnsibleFilterError: If collection name format is invalid
    """
    if not re.match(r'^[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+$', name):
        raise AnsibleFilterError(
            f"Invalid collection name format: '{name}'. "
            f"Expected format: namespace.collection (e.g., 'cloudkit.service')"
        )


class Collection(Base):
    """Collection represents an Ansible collection"""

    parent_path: Path
    name: str

    def read_metadata_for_role(self, path: Path) -> Metadata | None:
        """Read metadata for a role from cloudkit.yaml/yml file.

        Args:
            path: Path to the role directory

        Returns:
            Metadata object if found and valid, None otherwise
        """
        for filename in ["cloudkit.yaml", "cloudkit.yml"]:
            metadata_file: Path = path / "meta" / filename
            if metadata_file.exists():
                break
        else:
            display.vvv(f"No metadata file found for role at {path}")
            return None

        try:
            with metadata_file.open("r", encoding="utf-8") as fd:
                metadata = yaml.safe_load(fd)
        except yaml.YAMLError as e:
            display.warning(f"Failed to parse metadata file {metadata_file}: {e}")
            return None
        except (PermissionError, OSError) as e:
            display.warning(f"Error reading metadata file {metadata_file}: {e}")
            return None

        if metadata:
            try:
                return Metadata.model_validate(metadata)
            except Exception as e:
                display.warning(f"Invalid metadata in {metadata_file}: {e}")
                return None

        return None

    def read_params_for_role(self, path: Path) -> list[TemplateParameter]:
        """Read template parameters for a role from argument_specs.yaml/yml file.

        Args:
            path: Path to the role directory

        Returns:
            List of TemplateParameter objects, empty list if none found or on error.
            An empty list is valid - it means the role has no exposed parameters.
        """
        for filename in ["argument_specs.yaml", "argument_specs.yml"]:
            argspec_file = path / "meta" / filename
            if argspec_file.exists():
                break
        else:
            # No argument_specs file is valid - role may have no parameters
            return []

        try:
            with argspec_file.open("r", encoding="utf-8") as fd:
                argspec: AnsibleArgumentSpec = cast(
                    AnsibleArgumentSpec, yaml.safe_load(fd))
        except yaml.YAMLError as e:
            display.warning(f"Failed to parse argument_specs file {argspec_file}: {e}")
            return []
        except (PermissionError, OSError) as e:
            display.warning(f"Error reading argument_specs file {argspec_file}: {e}")
            return []

        template_params: list[TemplateParameter] = []

        # Navigate the nested structure to find template_parameters
        # Missing keys at any level are valid - just means no parameters defined
        for name, spec in (
            argspec.get("argument_specs", {})
            .get("main", {})
            .get("options", {})
            .get("template_parameters", {})
            .get("options", {})
            .items()
        ):
            try:
                template_params.append(TemplateParameter.from_argspec(name, spec))
            except Exception as e:
                display.warning(
                    f"Failed to parse template parameter '{name}' in {argspec_file}: {e}"
                )
                # Continue processing other parameters
                continue

        return template_params

    def templates(self) -> Generator[BaseTemplate, None, None]:
        """Generate Template objects for all roles in this collection.

        Yields:
            BaseTemplate objects (ClusterTemplate or ComputeInstanceTemplate) for each valid role found
        """
        roles_dir = self.parent_path / self.name.replace(".", "/") / "roles"

        # Validate roles directory exists
        if not roles_dir.exists():
            display.vvv(f"No roles directory found for collection '{self.name}' at {roles_dir}")
            return

        if not roles_dir.is_dir():
            display.warning(f"Expected directory but found file at {roles_dir}")
            return

        for path in roles_dir.glob("*"):
            # Only process directories (roles must be directories)
            if not path.is_dir():
                display.vvv(f"Skipping non-directory item in roles: {path.name}")
                continue

            metadata = self.read_metadata_for_role(path)
            params = self.read_params_for_role(path)
            if metadata is not None:
                try:
                    common = {
                        "collection": self.name,
                        "path": path,
                        "name": path.name,
                        "title": metadata.title,
                        "description": metadata.description,
                        "parameters": params,
                    }

                    if metadata.template_type == TemplateTypeEnum.cluster:
                        yield ClusterTemplate(
                            **common,
                            default_node_request=metadata.default_node_request,
                            allowed_resource_classes=metadata.allowed_resource_classes,
                        )
                    else:
                        yield ComputeInstanceTemplate(**common)
                except Exception as e:
                    display.warning(
                        f"Failed to create template for role '{path.name}' in collection '{self.name}': {e}"
                    )
                    continue


def find_template_roles(requested: list[str]) -> Generator[BaseTemplate, None, None]:
    """Find template roles in requested Ansible collections.

    Args:
        requested: List of collection names to search

    Yields:
        BaseTemplate objects (ClusterTemplate or ComputeInstanceTemplate) found in the collections
    """
    display.vv(f"Searching for templates in collections: {', '.join(requested)}")

    collections: list[Collection] = []
    for collection in requested:
        # Validate collection name format
        try:
            _validate_collection_name(collection)
        except AnsibleFilterError as e:
            display.warning(str(e))
            continue

        display.vvv(f"Querying ansible-galaxy for collection: {collection}")

        try:
            output = subprocess.check_output(
                [
                    "ansible-galaxy",
                    "collection",
                    "list",
                    collection,
                    "--format",
                    "json",
                ],
                stderr=subprocess.PIPE,
                timeout=30,
            )
            info: AnsibleCollectionList = cast(
                AnsibleCollectionList,
                json.loads(output)
            )
        except subprocess.TimeoutExpired:
            display.warning(
                f"Timeout querying ansible-galaxy for collection '{collection}' (30s limit exceeded)"
            )
            continue
        except subprocess.CalledProcessError as e:
            stderr_msg = e.stderr.decode('utf-8', errors='replace') if e.stderr else "No error output"
            display.warning(
                f"Failed to query collection '{collection}': {stderr_msg}"
            )
            continue
        except FileNotFoundError:
            raise AnsibleFilterError(
                "ansible-galaxy command not found. Ensure Ansible is properly installed."
            )
        except json.JSONDecodeError as e:
            display.warning(
                f"Invalid JSON response from ansible-galaxy for collection '{collection}': {e}"
            )
            continue

        if info:
            # If `ansible-galaxy collection list` finds the collection in multiple paths,
            # we will select the first one and warn the user.
            collection_paths = list(info.keys())

            if len(collection_paths) > 1:
                display.warning(
                    f"Collection '{collection}' found in multiple locations: {collection_paths}. "
                    f"Using first location: {collection_paths[0]}"
                )

            collection_path = Path(collection_paths[0])
            display.vvv(f"Found collection '{collection}' at {collection_path}")
            collections.append(
                Collection(parent_path=collection_path, name=collection)
            )
        else:
            display.vv(f"Collection '{collection}' not found")

    for collection in collections:
        yield from collection.templates()


def find_template_roles_filter(template_type: TemplateTypeEnum):
    """Factory function that returns a filter for the specified template type.

    Args:
        template_type: The type of template to filter for

    Returns:
        A filter function that accepts a list of collection names and returns
        matching template role dictionaries
    """
    def filter_func(requested: list[str]) -> list[dict[str, Any]]:
        try:
            roles = (
                role for role in find_template_roles(requested)
                if role.template_type == template_type
            )
            result = [
                role.model_dump(by_alias=True, exclude_none=True)
                for role in roles
            ]
            display.vv(f"Returning {len(result)} {template_type} template(s)")
            return result

        except AnsibleFilterError:
            raise
        except Exception as e:
            display.error(f"Unexpected error in find_template_roles filter: {e}")
            raise AnsibleFilterError(f"Template discovery failed: {str(e)}")

    return filter_func


class FilterModule:
    """Ansible filter plugin for finding template roles."""

    def filters(self) -> dict[str, Any]:
        """Return the available filter functions.

        Returns:
            Dictionary mapping filter names to filter functions
        """
        return {
            "find_cluster_template_roles": find_template_roles_filter(TemplateTypeEnum.cluster),
            "find_compute_instance_template_roles": find_template_roles_filter(TemplateTypeEnum.compute_instance),
        }


if __name__ == "__main__":
    import sys

    # Usage: python find_template_roles.py --type cluster|compute_instance collection1 collection2 ...
    if "--type" not in sys.argv:
        print("Error: --type parameter is required", file=sys.stderr)
        print("Usage: python find_template_roles.py --type cluster|compute_instance collection1 collection2 ...", file=sys.stderr)
        sys.exit(1)

    type_idx = sys.argv.index("--type")
    if type_idx + 1 >= len(sys.argv):
        print("Error: --type requires a value (cluster or compute_instance)", file=sys.stderr)
        sys.exit(1)

    template_type = sys.argv[type_idx + 1]
    collections = sys.argv[1:type_idx] + sys.argv[type_idx + 2:]

    if not collections:
        print("Error: At least one collection name is required", file=sys.stderr)
        print("Usage: python find_template_roles.py --type cluster|compute_instance collection1 collection2 ...", file=sys.stderr)
        sys.exit(1)

    if template_type == TemplateTypeEnum.cluster:
        filter_func = find_template_roles_filter(TemplateTypeEnum.cluster)
    elif template_type == TemplateTypeEnum.compute_instance:
        filter_func = find_template_roles_filter(TemplateTypeEnum.compute_instance)
    else:
        print(f"Error: Invalid template type '{template_type}'. Must be 'cluster' or 'compute_instance'", file=sys.stderr)
        sys.exit(1)

    found = filter_func(collections)
    print(json.dumps(found))
