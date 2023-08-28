from dataclasses import dataclass


@dataclass
class SSMArgs:
    parameters: dict[str, str]


@dataclass
class SSMExports:
    parameter_names: list[str]
