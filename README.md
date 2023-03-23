# Echo:NPC for Regolith

Echo:NPC is a json-based templating language for creating powerful state-driven Bedrock Entities, including NPCs, tutorials, event-entities and quests.

 - [Visit the Echo:NPC Website.](https://sirlich.github.io/echo-npc-documentation/)
 - [Install the VSCode Extension](https://marketplace.visualstudio.com/items?itemName=SirLich.echo-validate)

## What is Regolith?

Regolith is an Addon Compiler for the Bedrock Edition of Minecraft, and is the underlying program required for this filter to run.

 - [Visit the Regolith Website.](https://bedrock-oss.github.io/regolith/)

## How to use this filter:

If you get stuck, visit the Regolith website for more information. The general idea is:
 - `regolith init` (if you don't have a project yet)
 - `regolith install`
 - Add the `filter` into a profile of your choosing (see `config.json`)

The filter definition looks like this

```json
{
	"filter": "echo"
}
```

When installing, some default data will be placed into `data/echo`. After installing, you can edit these files yourself :)
## Folder Structure

This filter expects and uses these paths:

In general, the path `data/echo` is used to store all configurations for Echo. Settings go in `settings`, and template files go in `templates`. When this filter runs, all the templates will be compiled.

```
packs
└─ data
   └─ echo
      ├─ settings
      │   └─ settings.json
      └─ templates
          └─ example_template.json
```
