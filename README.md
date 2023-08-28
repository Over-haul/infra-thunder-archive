---
nav_order: 0
has_children: true
---

# Thunder

Opinionated multi-cloud infrastructure orchestration.

Go from zero to production-grade infrastructure with Kubernetes easily!

[Read the Docs on Github Pages for a better experience!](//over-haul.github.io/infra-thunder)
{: .d-none}

## What is this?

Thunder is a collection of reusable Pulumi Python modules that create infrastructure in cloud providers.

## Common Commands

Need a quick reference? We'll put this at the top for you.  
No idea what Pulumi or Thunder are? Skip this section and move on - we'll explain it all, we promise!

| command | description |
| --- | --- |
| `pulumi stack select` | Change from stack to stack in a project |
| `pulumi preview` | Show a preview of the stack to be applied |
| `pulumi preview --diff` | Show detailed preview including resource properties (similar to `terraform plan` output) |
| `pulumi config` | Show the config for the currently selected stack |

## Topics

The Readme for Thunder is pretty long, so we've split it up for you into a few separate pages

- [Concepts](README.Concepts.md) - All about the concepts that make Thunder work.
- [Quickstart](README.Quickstart.md) - Had enough about the theory? Jump in and build some infrastructure!
- [Configuration](README.Configuration.md) - Want to tweak or tune Thunder? This document will help.
- [Best Practices](README.BestPractices.md) - Need to set up a Thunder system from scratch? Thou shalt read me.
- [Programming](README.Programming.md) - Really want to build some infrastructure? Start here.

Thunder supports multiple different modules, and each module has its own documentation.
See the front page for each of the module types here:

- [AWS Modules](README.Modules.AWS.md)
- [Azure Modules](README.Modules.Azure.md)

## License

[MIT No Attribution](https://choosealicense.com/licenses/mit-0/#)
