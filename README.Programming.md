---
parent: Thunder
nav_order: 2
---

# Thunder Programming Guide

```text
TODO: Write a better programming guide
- The Sign Painter
```

That *Sign Painter* guy sure is lazy...

In the meantime, here's a rough overview.

## Rough Overview

Thunder modules typically are structured like this:

```shell
.
└── infra_thunder/
    └── aws/
        └── dns/
            ├── __init__.py
            ├── config.py
            ├── launcher.py
            └── dns.py
```

- `__init__.py` should contain minimal code. Something like this should be all that's necessary:

  ```python
  from .dns import DNS
  from .launcher import launcher
  ```

- `config.py` is where your `dataclass` objects exist for configuring your module.
- `launcher.py` is where your template should be concerned with reading Pulumi's `Config` object to parse the YAML
  for the stack currently being created. A lot of glue code will live here, and will be simplified significantly in
  the future once we decide on a object mapper library.
- `dns.py` is your class, and it should expose a subclass object of Pulumi's `ComponentResource`. See one of the
  existing modules for some direction on what one of those should look like.

Any time a new module is added, a reference should be added to the module's launcher in `infra_thunder/aws/launcher.py`.

### URN names

Typical Pulumi resources are structured like:

```shell
urn:pulumi:aws-us-west-2::vpc::pkg:thunder:vpc$aws:ec2/subnet:Subnet::lb-us-east-1b
           ^^^^^^^^^^^^^  ^^^  ^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^
           |              |    └----------|    └--------|             └--|
           <stack-name>   <project-name>  <parent-type> <resource-type>  <resource-name>
```

This allows you to use `ComponentResource`s to create bundles of components (`pkg:thunder:vpc` in the above case),
and resources that exist in your template directly without them overlapping with each other.
