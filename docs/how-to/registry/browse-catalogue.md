---
title: Browse the module catalogue
description: Find an nf-core module, see whether the registry holds it, and open an imported tool.
---

# Browse the module catalogue

The **Registry** tab lists every nf-core module beside the registry the builder uses, so you
can see which tools the builder can already choose and which ones it cannot.

## Find a module

1. Open **Registry**. The catalogue lists every module that nf-core publishes.
2. Narrow the list with the filters on the left:
   - **In the registry**: the module's state (below).
   - **Topic**: genomics, alignment, assembly and so on.
   - **Reads or makes**: a file format the module takes or produces.
3. Or search by name, tool, format or what the module does. Search matches the words you
   type exactly, so `%` and `_` are ordinary characters.
4. Pick a row. The panel on the right shows what the module reads and makes, its tool version,
   its state and a link to its source on nf-core.

The filters, the search and the selected row are kept in the address, so you can share a link
to the view you are looking at.

## What each state means

| State | Meaning |
|---|---|
| Imported | The registry holds this module at the same tool version that nf-core packages. |
| Update available | The registry holds it, but nf-core now packages a different tool version. The panel shows both. |
| Unknown version | The registry holds it, but nf-core's tool version could not be read from the module's `environment.yml`. |
| Gone upstream | The registry holds it, but nf-core no longer has a module at that path. |
| Not imported | The registry does not hold it yet. |

A module's tool version comes from the conda package named for its tool. When no package
matches, or more than one does, the version is shown as unknown instead of being guessed.

!!! note "Not built yet"
    *In review* and *Merged, not released* are listed with no modules in them. They will
    show forge pull requests once publishing exists (issue 366). Until then, a registry change
    still goes through a pull request on `comeni-registry`, written by hand.

## Open an imported tool

Choose **Open the tool** in the panel. The tool page shows what the registry records about the
tool:

- the ports it reads and makes, with their states;
- each setting with its default, or *asks the person*, and the reason for it;
- the rules that decide when the builder chooses it;
- where it comes from: the nf-core commit, the container, who approved it and when, and which
  registry the builder loaded it from;
- nf-core's current description and version of the module.

!!! note "Not built yet"
    Adding tests to a tool (issue 365) is drawn on the tool page but cannot be used yet.

To bring a module in, [forge it](forge-a-tool.md); to write a contract entirely by hand, follow
[Writing a contract](add-tool.md).

## Keep the catalogue current

The catalogue syncs from nf-core once a day. Choose **Sync now** in the list's footer to sync
straight away. If a sync fails, for example because there is no network, the catalogue keeps
what the last successful sync read and the footer says that it is stale and why.
