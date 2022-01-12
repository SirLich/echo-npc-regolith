import json
import sys
import os
import copy
import re
import traceback
from colorama import Fore, Back, Style
from colorama import init
import shlex
import ast
init(autoreset=True)


"""
Constants
"""

VERSION = "2.1"


"""
Printing and Debugging
"""

def warning(message):
    print(Fore.YELLOW +  "WARNING:" + Style.RESET_ALL  + " " + message)

def warn(message):
    print(Fore.YELLOW +  "+:" + Style.RESET_ALL + " " + message)

def err(message):
    print(Fore.RED +  "+:" + Style.RESET_ALL + " " + message)

def error(message):
    print(Back.RED + Fore.BLACK +  "ERROR:" + Fore.RED + Back.RESET  + " " + message)

def message(message, watch=False):
    print(Fore.LIGHTCYAN_EX + message)

def debug_traceback():
    track = traceback.format_exc()
    print(track)
    sys.exit(1)

def list_to_string(allowed):
    s = ""
    for element in allowed:
        s += str(element) + ", "
    s = s[:-2]
    return s

# This simply warns you if the dict contains keys that aren't allowed
def warn_bad_keys(state, allowed):
    allowed.sort()
    for key in state.keys():
        if key not in allowed:
            error("Bad key found!")
            err("Key: " + key)
            err("Allowed: " + list_to_string(allowed))
            err("Did you misspell something? For example `texts` instead of `text`?")
            return debug_traceback()

"""
Dictionary handling, io
"""

def get_echo_path():
    return os.path.join(os.getcwd(), "data", "echo")
    
#Safely gets json code that might contain comments
#Credit: https://stackoverflow.com/questions/29959191/how-to-parse-json-file-with-c-style-comments
def get_json_from_file(fh):
    contents = ""
    for line in fh:
        cleanedLine = line.split("//", 1)[0]
        if len(cleanedLine) > 0 and line.endswith("\n") and "\n" not in cleanedLine:
            cleanedLine += "\n"
        contents += cleanedLine
    fh.close
    while "/*" in contents:
        preComment, postComment = contents.split("/*", 1)
        contents = preComment + postComment.split("*/", 1)[1]
    return json.loads(contents)

def merge_dicts(a, b, path=None):
    "merges b into a"
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dicts(a[key], b[key], path + [str(key)])
            elif isinstance(a[key], list) and isinstance(b[key], list):
                a[key] = a[key] + b[key]
            elif a[key] == b[key]:
                pass # same leaf value
            else:
                raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
        else:
            a[key] = b[key]
    return a

def get_output_locations(store, local_base):
    # Split path and generate base, and local name
    _, tail = os.path.split(local_base)
    tail = tail.replace(".json","")

    entity_name = fetch_setting("entity_name_format", store).replace("NAME", tail)
    animation_name = fetch_setting("animation_controller_name_format", store).replace("NAME", tail)

    # Base will be our behavior pack
    base = "BP"

    # Create sub-path structure from settings
    entity_subpath = fetch_setting("entity_subpath", store).replace("/","\\")
    anim_subpath = fetch_setting("animation_controller_subpath", store).replace("/","\\")
    subpath = fetch_setting("subpath", store).replace("/","\\")

    if(entity_subpath == ""):
        entity_subpath = subpath
    
    if(anim_subpath == ""):
        anim_subpath = subpath

    # Create actual paths
    entity_path = os.path.join(base, "entities", entity_subpath)
    anim_path = os.path.join(base, "animation_controllers", anim_subpath)

    if not os.path.exists(entity_path):
        warning("Entity path does not exist. Creating...")
        warn(entity_path)
        os.makedirs(entity_path)
    
    if not os.path.exists(anim_path):
        warning("Animation controller path does not exist. Creating...")
        warn(anim_path)
        os.makedirs(anim_path)

    return os.path.join(entity_path, entity_name), os.path.join(anim_path, animation_name)

# Coerces string-like to bool/float
def coerce_types(value):
    true_type = ["true"]
    false_type = ["false"]
    
    try:
        if value.startswith("{") and value.endswith("}") or value.startswith("[") and value.endswith("]"):
            return ast.literal_eval(value)
        elif value.lower() in true_type:
            return True
        elif value.lower() in false_type:
            return False
        else:
            v = float(value)
            if v.is_integer():
                return int(v)
            return v
    except Exception:
        return value

#Fetches settings data.
#If combine is set as True, then it will push the results into a dictionary, instead of replacing.
def fetch_setting(name, store, **kwargs):
    try:
        header = store.get("header", {})
        settings = store.get("settings", {})
        custom_settings = store.get("custom_settings", {})
        configs = store.get("configs", {})
        project_settings = store.get("project_settings", {})

        if(kwargs.get("combine", False) == True):
            data = {}
            data.update(header.get(name, {}))
            data.update(settings.get(name, {}))
            data.update(custom_settings.get(name, {}))
            data.update(configs.get(name, {}))
            data.update(project_settings.get(name, {}))
            if(data == None):
                raise Exception("Missing setting value")
            return data
        else:
            data = header.get(name, project_settings.get(name, custom_settings.get(name, configs.get(name, settings.get(name)))))

            if(data == None):
                raise Exception("Missing setting value")
            return data
    except Exception:
        error("Could not fetch setting!")
        err("Name: " + name)
        err("Did you delete something important from settings.json?")
        err("Did you recently upgrade your .exe, without replacing your .settings file?")
        return debug_traceback()

#Store = store
#Group = top level fetch request
#Name = What we are searching for
#Argv = What we are replacing

def smart_fetch_json(store, group, name, argv, next_event):
    try:
        snippets = fetch_setting(group, store, combine=True)

        #Take a copy -not the real snippet.
        shallow = snippets.get(name)
        if(shallow == None): 
            error("Could not fetch snippet!")
            err("Name: " + name)
            err("Type: " + group)
            err("Arguments: " + str(argv))
            return debug_traceback()

        snippet = copy.deepcopy(shallow)

        #Set wildcards
        snippet = set_wildcards(snippet, argv, next_event)
        return snippet
    except Exception:
        error("Could not locate template!")
        err("Type: " + group)
        err("Name: " + name)
        err("Arguments: " + str(argv))
        return debug_traceback()

#This checks whether a number exists inside a "numbery argument":
# does 15 exist in "1-5, 9, 12" (no)
def check_match(check, number, final):
    matches = set()
    args = check.split(",")
    for a in args:
        a = replace_words_with_numbers(a, final)
        #check a range
        if("-" in a):
            min, max = a.split("-")
            for i in range(int(min), int(max) + 1):
                matches.add(i)
        elif(a == "all"):
            matches.update(range(0, final + 1))
        else:
            matches.add(int(a))
    return number in matches

#This extracts the list elements that match the number args, per ^
def extract_matches(arguments, number, final, list_name):
    if(isinstance(arguments, list)):
        try:
            #We index by one, so we need this
            if(isinstance(arguments[number - 1], list) or isinstance(arguments[number - 1], dict)):
                return [arguments[number - 1]]
            else:
                return [[arguments[number - 1]]]
        except:
            error("List index out of range!")
            err("This means that you provided something in a list, and didn't provide enough elements!")
            err("The list was called: {}".format(list_name))
            err("The '{}' list contained {} item: {}".format(list_name, len(arguments), str(arguments)))
            err("Echo was attempting to access item number {}.".format(number))
            err("The '{}' list must provide {} items (the total number of sub-states).".format(list_name, final))
            err("Consider converting the '{}' list to set-lang format.".format(list_name))
            return debug_traceback()
    e = []
    for item in arguments.items():
        if(check_match(item[0], number, final)):
            if(isinstance(item[1], list) or isinstance(item[1], dict)):
                e.append(item[1])
            else:
                e.append([item[1]])
    return e

#Smartly updates components, to handle merging.
def smart_update(components, new_component):
    #List of mergable components
    mergable = [
        "minecraft:environment_sensor",
        "minecraft:interact"
    ]

    key = list(new_component.keys())[0]

    #Custom merge code
    if(key in components and key in mergable):
        #Environment Sensor handling
        if(key == "minecraft:environment_sensor"):
            if(new_component.get(key).get("triggers") == None):
                error("Missing `triggers` definition in component: minecraft:environment_sensor!")
                err("environment_sensors defined in templates need to include a triggers list.")
                return debug_traceback()
            
            #If defined correctly, merge in:
            triggers = new_component.get(key).get("triggers")
            for component in triggers:
                components.get("minecraft:environment_sensor").get("triggers").append(component)
        if(key == "minecraft:interact"):
            if(new_component.get(key).get("interactions") == None):
                error("Missing `interactions` definition in component: minecraft:interact!")
                err("interacts defined in templates need to include a interactions list.")
                return debug_traceback()
            
            #If defined correctly, merge in:
            interactions = new_component.get(key).get("interactions")
            for component in interactions:
                #WRONG WRONG WRONG
                components.get("minecraft:interact").get("interactions").append(component)
    else:
        #This is the simple case, no merging required
        components.update(new_component)

def set_wildcards(obj, values, next_event):
    if(isinstance(obj, dict)):
        for k, v in obj.items():
            obj[k] = set_wildcards(v, values, next_event)
    elif(isinstance(obj, list)):
        for i in range(len(obj)):
            obj[i] = set_wildcards(obj[i], values, next_event)
    elif(isinstance(obj, str)):
        #Regular expression
        full_reg = r'\$(?P<index>\d*)\{(?P<inner>.*)\}'
        simple_reg = r'\$(?P<index>\d+)'

        #Build match
        match = re.search(full_reg, obj)

        #Match exists. Lets find and replace!
        if(match != None):
            index = match.group('index')
            inner = match.group('inner')
            
            #Set to next event, as needed
            if(inner == "next_event"):
                inner = next_event

                #Return on null value:
                if(inner == None):
                    warning("This state does not have a declared transition, so the automatic conversion of {} cannot take place".format(obj))
                    
            
            #Testing for length/size
            if(int(index) <= len(values)):
                value = values[int(index) - 1]

            #Use default, since the supplied values aren't enough     
            else:
                value = inner

            obj = coerce_types(re.sub(full_reg, value, obj))
            return obj
        
        #Try again, with simpler match!
        match = re.search(simple_reg, obj)
        if(match != None):
            index = match.group('index')
            
            #Testing for length/size
            if(int(index) <= len(values)):
                value = values[int(index) - 1]
            else:
                error("Not enough arguments supplied to template!")
                err("Arguments supplied: " + str(values))
                err("Attempting to replace: " + obj)
                err("Template:")
                return debug_traceback()

            obj = coerce_types(re.sub(simple_reg, value, obj))
    return obj


def create_store(file_location):
    try:
        #Header
        with open(file_location) as template_file:
            try:
                template = get_json_from_file(template_file)
            except Exception as e:
                error("JSON error in template file!")
                err("Please check the correctness of your template.")
                err("File: " + file_location)
                err(str(e))
                return debug_traceback()
                
        # Header
        header = template.get("header", {})

        # Project
        project_settings = {}
        for project_name in header.get("projects", []):
            project_path = os.path.join(get_echo_path(), "settings", "projects", project_name).replace("/","\\") + ".json"
            if os.path.isfile(project_path):
                with open(project_path) as project_file:
                    project_settings = merge_dicts(project_settings, get_json_from_file(project_file))
            else:
                error("Project cannot be found: " + project_name)
                err("Confirm that this file exists: " + project_path)
                return debug_traceback()

        # Settings

        with open(os.path.join(get_echo_path(), "settings", "settings.json")) as settings_file:
            settings = get_json_from_file(settings_file)

        # Custom Settings
        custom_settings = {}
        custom_settings_path = os.path.join(get_echo_path(), "settings", "custom_settings.json")
        if os.path.isfile(custom_settings_path):
            with open(custom_settings_path) as custom_settings_file:
                custom_settings = get_json_from_file(custom_settings_file)
        
        # Config
        configs = {}
        config_path = os.path.join(get_echo_path(), "settings", "configs")
        if os.path.isdir(config_path):
            for filename in os.listdir(config_path):
                with open(os.path.join(config_path, filename)) as config:
                    configs = merge_dicts(configs, get_json_from_file(config))
        
        # Temp store, which we use for getting the entity details
        store = {
            "settings": settings,
            "custom_settings": custom_settings,
            "header": header,
            "configs": configs,
            "project_settings": project_settings
        }

        #Allow shortcutting, using entity_templates
        entity = template.get("entity")

        #Use entity templates, if available
        if(isinstance(entity, str)):
            name, args = entity.split(" ")[0], shlex.split(entity)[1:]
            entity = smart_fetch_json(store, "entity_templates", name, args, "INVALID")

        #Create global name variables.
        try:
            entity_name = entity["minecraft:entity"]["description"]["identifier"]
        except:
            error("Template does not contain 'entity' key.")
            err("Echo:NPC requires every template to define an entity key.")
            err("Check your template for misspellings, or a missorderings.")
            return debug_traceback()


        simple_entity_name = entity_name.replace(":","_").replace(".","_")
        controller_name = "controller.animation." + simple_entity_name

        #Create store, which bundles all read-only-data together.
        return {
            "template": template,
            "settings": settings,
            "custom_settings": custom_settings,
            "header": header,
            "configs": configs,
            "project_settings": project_settings,
            "entity_name": entity_name,
            "simple_entity_name": simple_entity_name,
            "controller_name": controller_name,
            "entity": entity
        }
    except:
        error("Could not open files. This suggests a config/setup issue.")
        err("Does settings/settings.json exist?")
        err("Does settings/custom_settings.json exist?")
        err("Does the template exist?")
        return debug_traceback()

def replace_words_with_numbers(a, final):
    return a.replace("first", "1").replace("last", str(final + 1)).replace("second", "2").replace("end", str(final + 1)).replace("final", str(final + 1))

def get_length_of_argument(state, argument):
    total_length = 0
    check = state.get(argument)
    if(check == None):
        pass
    elif(isinstance(check, list)):
        total_length =  len(check)
    elif(isinstance(check, dict)):
        maxfound = 0
        for item in check.items():
            args = item[0].split(",")
            for a in args:
                a = replace_words_with_numbers(a, 0)
                if(a == "all"):
                    continue
                if("-" in a):
                    left, right = a.split("-")
                    left = int(left)
                    right = int(right)

                    #Skip arguments containing ALL or END or whatever
                    if(left >= right):
                        continue

                    maxfound = max(maxfound, right)
                else:
                    maxfound = max(maxfound, int(a))
        total_length = maxfound
    return total_length
    
def get_state_length(state):
    length = max(
        get_length_of_argument(state, "text"),
        get_length_of_argument(state, "sound"),
        get_length_of_argument(state, "commands"),
        get_length_of_argument(state, "transitions"),
        get_length_of_argument(state, "sounds"),
        get_length_of_argument(state, "custom_components"),
        get_length_of_argument(state, "components"),
        1
    )
    return state.get("length", length)

def handle_file(file_location):
    try:
        store = create_store(file_location)
        entity = store.get("entity")
        entity_name = store.get("entity_name")
        controller_name = store.get("controller_name")
        template = store.get("template")
    except Exception as e:
        error("Could not create data store")
        return debug_traceback()

    anim_controller = {
        "format_version": "1.10.0",
        "animation_controllers": {
            store.get("controller_name"): {
                "states": {

                }
            }
        }
    }

    message("Loaded entity: " + Fore.GREEN + entity_name + Fore.RESET + " in file " + Fore.GREEN + str(file_location), watch=True)
    warn_bad_keys(template, ["states", "header", "entity", "custom_components", "components", "randomizers", "on_death"])

    #Create new files (so we don't overwrite anything)
    entity_loc, anim_loc = get_output_locations(store, file_location)
    
    #Try/Catch for debugging reasons.
    try:
        new_entity_file = open(entity_loc, "w+")
    except Exception as e:
        error("Could not create entity file.")
        err("This is usually because the behavior pack file doesn't have an 'entities' folder.")
        return debug_traceback()
    try:
        new_anim_controller_file = open(anim_loc,"w+")
    except Exception as e:
        error("Could not create entity animation controller file.")
        err("This is usually because the behavior pack file doesn't have an 'animation_controllers' folder.")
        return debug_traceback()

    #Only create target if the target is set in custom_settings or the entity header.
    #False is the default value in settings.json

    extra_entities = fetch_setting("create_entities", store)
    tail, _ = os.path.split(entity_loc)
    for e in extra_entities:
        try:
            name, args = e.split(" ")[0], shlex.split(e)[1:]
            output_loc = os.path.join(tail, fetch_setting("entity_name_format", store).replace("NAME", args[0].replace(":", ".")))
            new_target_file = open(output_loc,"w+")
            target = smart_fetch_json(store, "entity_templates", name, args, "INVALID")
            json.dump(target, new_target_file, indent=4, ensure_ascii=False)
            new_target_file.close()
        except Exception:
            error("Could not create entity.")
            err("Tried to create: " + e)
            err("This could be caused by a misspelled entity template.")
            return debug_traceback()

    #Create animations/scripts support, in case it wasn't defined in the normal entity
    description = entity.get("minecraft:entity").get("description")

    if("scripts" not in description):
        description["scripts"] = {}

    if("animate" not in description.get("scripts")):
        description["scripts"]["animate"] = []
        
    if("animations" not in description):
        description["animations"] = {}

    #Add animation data
    description["scripts"]["animate"].append(entity_name + "_commands")
    entity["minecraft:entity"]["description"]["animations"][entity_name + "_commands"] = controller_name

    # These lists are used to generate all kinds of things later. Adding stuff here
    # will directly effect what events, components, and animation states are created.
    event_names = []
    state_names = []
    event_commands = []
    state_components = []
    state_component_groups = []

    #Loop through each state, handling them all individually (and per type)
    #The goal here is to fill up the lists above, which will then be placed into the json
    #Each state_type will add stuff to the lists in their own way.
    message("Handling states:")

    default_state = fetch_setting("default_state", store)

    sound_template = fetch_setting("sound_template", store)
    text_template = fetch_setting("text_template", store)

    #Prefill the custom_components
    for custom_component in template.get("custom_components", {}):
        split = shlex.split(custom_component)
        transition, args = split[0], split[1:]
        smart_update(entity["minecraft:entity"]["components"], smart_fetch_json(store, "component_templates", transition, args, ""))

    #Components
    if(template.get("components") != None):
        smart_update(entity["minecraft:entity"]["components"], template.get("components", {}))

    states = template.get("states", [])
    if states == []:
        warning("Entity will be created with no states!")
        warn("Your entity either didn't define a 'states' key, or the states were empty.")
        warn("Please carefully check your template to ensure this was intended.")
    for state in states:
        #Collect state type, so we know how to handle it!
        #State type "none" will be treated as no state type at all.
        state_type = state.get("type", fetch_setting("default_state_type", store))
        try:
            simple_state_name = str(state["name"])
            bad_state_names = ["clear", "despawn"]
            if simple_state_name in bad_state_names:
                error("Attemping to create a state with an invalid name.")
                err("Sorry! Some state names are reserved for use by Echo:NPC")
                err("Reserved state names: {}".format(str(bad_state_names)))
                return debug_traceback()
        except Exception as e:
            error("Missing state name!")
            err("All states should contain a 'name' field.")
            return debug_traceback()

        state_name = "echo:state_" + simple_state_name
        message(simple_state_name)
        #Standard Format 
        if(state_type == "standard"):
            warn_bad_keys(state, ["next", "length", "commands", "components", "custom_components", "transitions", "sounds", "text", "name", "type"])
            final_transition = state.get("next")
            length = get_state_length(state)
            #length = state.get("length", len(state.get("text", "")))
            if(length == 0):
                length = 1
                warning("No text list was provided, and no length was set.")
                warn("Length of the state will be set to 1.")
                warn("Sub-states or arrays longer than 1 will not be proccessed.")
                warn("Consider adding a 'length' argument.")


            #Loop through each standard chat and handle it.
            for i in range(length):

                #Base commands
                commands = []

                #Component groups
                component_groups = []

                #Add components groups
                for match in extract_matches(state.get("component_groups", {}), i + 1, length, "component_groups"):
                    component_groups.extend(match)

                #Handle components first
                components = {}

                #Add components

                for match in extract_matches(state.get("components", {}), i + 1, length, "components"):
                    smart_update(components, match)
                    
                #Setup state and event name. Note that state 0 is marked as the actual state: echo:explode. not echo:explode_0
                if(i == 0):
                    event_name = "echo:event_" + simple_state_name
                    state_name = "echo:" + simple_state_name
                else:
                    event_name = "echo:event_" + simple_state_name + "_" + str(i + 1)
                    state_name = "echo:" + simple_state_name + "_" + str(i + 1)

                message(" > " + Fore.RESET + state_name)
                state_names.append(state_name)

                #The last event should be treated special!
                if(i == length - 1):
                    try:
                        next_event_name = "echo:" + final_transition
                    except Exception:
                        next_event_name = None
                else:
                    next_event_name = "echo:" + simple_state_name + "_" + str(i + 2)

                event_names.append(event_name)

                #Custom component handling.
                for match in extract_matches(state.get("custom_components", {}), i + 1, length, "custom_components"):
                    for component in match:
                        split = shlex.split(component)
                        transition, args = split[0], split[1:]
                        smart_update(components, smart_fetch_json(store, "component_templates", transition, args, event_name))

                #Start transition types start blank, but will be seeded from transitions, and fallback to default transitions
                transition_types = []
                
                #Gather custom_transition_types.
                for match in extract_matches(state.get("transitions", {}), i + 1, length, "transitions"):
                    transition_types.extend(match)
                
                #Add default transition_types if transition types is empty
                if(transition_types == []):
                    transition_types = fetch_setting("default_transitions", store)

                #Handles interact, timer, proximity, reverse_proximity.
                for t in transition_types:
                    transition, args = t.split(" ")[0], shlex.split(t)[1:]
                    message("    - " + Fore.RESET + transition)

                    #Add custom commands for some transitions:
                    if(transition == "has_tag"):
                        commands.append("/tag @s remove " + args[0])

                    smart_update(components, smart_fetch_json(store, "transition_templates", transition, args, event_name))
                
                #The things to ignore
                notlist = ["", "skip", "none"]

                #Sounds
                for match in extract_matches(state.get("sounds", {}), i + 1, length, "sounds"):
                    for sound in match:
                        if(sound not in notlist):
                            commands.append(sound_template.replace("SOUND", sound))

                #Add Text
                for match in extract_matches(state.get("text", {}), i + 1, length, "text"):
                    for text in match:
                        if(text not in notlist):
                            commands.append(text_template.replace("TEXT", text))
                            
                #Add components
                for match in extract_matches(state.get("commands", {}), i + 1, length, "commands"):
                    for command in match:
                        if command.startswith("!"):
                            transition, args = command.split(" ")[0][1:], shlex.split(command)[1:]
                            custom_commands = smart_fetch_json(store, "command_templates", transition, args, event_name)
                            if(isinstance(custom_commands, list)):
                                commands.extend(custom_commands)
                            else:
                                commands.append(custom_commands)
                        else:
                            commands.append(command)

                #Add clear:
                commands.append("@s echo:clear")

                #Add optional transition
                if(next_event_name != None):
                    commands.append("@s " + next_event_name)

                #Add components
                for match in extract_matches(state.get("events", {}), i + 1, length, "events"):
                    for arg in match:
                        commands.append("@s " + arg)

                ## Add Date we've saved up:

                #Append commands
                event_commands.append(commands)

                #Append components
                state_components.append(components)

                #Append component groups
                state_component_groups.append(component_groups)



        #+++++++++++++++++++++++++++++++ SINGLE +++++++++++++++++++++++++
        elif(state_type == "single"):
            #Commands handling
            commands = []
            commands.append("@s echo:clear")

            for command in state.get("commands", []):
                if command.startswith("!"):

                    transition, args = command.split(" ")[0][1:], shlex.split(command)[1:]
                    custom_commands = smart_fetch_json(store, "command_templates", transition, args, "NO_VALID")

                    if(isinstance(custom_commands, list)):
                        commands.extend(custom_commands)
                    else:
                        commands.append(custom_commands)
                else:
                    commands.append(command)
            
            #TODO
            state_component_groups.append([])

            commands.append("@s " + state_name)

            #Naming
            name = state.get("name")
            event_name = "echo:" + name
            state_name = "echo:state_" + name
            event_names.append(event_name)
            state_names.append(state_name)

            components = {}
            components.update(state.get("components", {}))

            for t in state.get("transitions", []):
                transition, args = t.split(" ")[0], shlex.split(t)[1:]
                message(" - " + Fore.RESET + transition)
                smart_update(components, smart_fetch_json(store, "transition_templates", transition, args, event_name))

            for match in state.get("custom_components", []):
                split = shlex.split(match)
                transition, args = split[0], split[1:]
                smart_update(components, smart_fetch_json(store, "component_templates", transition, args, event_name))

            state_components.extend([components])
            event_commands.append(commands)

        else:
            error("Unsupported state type: " + state_type)
            err("Supported: standard, single")
            return debug_traceback()

    #NOW THAT THE DATA HAS BEEN COLLECTED, WE NEED TO PUT IT INTO THE ACTUAL JSON ##
    #===============================================================================#

    if entity["minecraft:entity"].get("component_groups") == None:
        entity["minecraft:entity"]["component_groups"] = {}
    
    if entity["minecraft:entity"].get("events") == None:
        entity["minecraft:entity"]["events"] = {}

    #Add component groups (the main thing that has to happen1!)
    for i in range(len(state_components)):
        entity["minecraft:entity"]["component_groups"][state_names[i]] = state_components[i]

    # A none default state will simply not overwrite the entity spawned
    if(default_state != "none"):
        
        #Incorrect default state
        available_default_states = state_names + event_names + list(template.get("randomizers", {}).keys())
        available_default_states = [w.replace('echo:', '') for w in available_default_states]

        if(default_state not in available_default_states):
            error("Default state does not exist.")
            err("Default state: " + default_state)
            err("Available states: ")
            for x in available_default_states:
                err("- " + x.replace("echo:", ""))
            return debug_traceback()

        entity_spawned = entity.get("minecraft:entity",{}).get("events", {}).get("minecraft:entity_spawned", {})

        spawn_events = entity_spawned.get("add", {}).get("component_groups", [])
        spawn_events.append("echo:" + default_state)

        if entity_spawned == {}:
            # Make from scratch
            entity["minecraft:entity"]["events"]["minecraft:entity_spawned"] = {
                "add": {
                        "component_groups": spawn_events
                    }
                }
        else:
            entity_spawned["add"] = {}
            entity_spawned["add"]["component_groups"] = []
            entity_spawned["add"]["component_groups"] = spawn_events

            entity["minecraft:entity"]["events"]["minecraft:entity_spawned"] = entity_spawned

    else:
        warning("Default state set to None."),
        warn("Entity will need to be spawned with a spawn event.")

    #"echo:clear command!"
    #List of states to remove
    entity["minecraft:entity"]["events"]["echo:clear"] = {
        "add": {
                "component_groups": [
                    "echo:execute_no_command"
                ]
            },
            "remove": {
                "component_groups": state_names.copy()
            }
        }
    
    #Add echo:despawn command!
    entity["minecraft:entity"]["events"]["echo:despawn"] = {
        "add": {
                "component_groups": [
                    "echo:despawn"
                ]
            }
        }

    #Add GOTO events based on state name!!
    for i in range(len(state_names)):
        event_name = state_names[i]
        state_name = state_names[i]

        #Add component groups from the state component groups
        component_group = [state_name]
        component_group.extend(state_component_groups[i])

        event = {
				"add": {
                    "component_groups": component_group
                }
			}
        
        entity["minecraft:entity"]["events"][event_name] = event
    
    #Add command events!
    for event_name in event_names:
        event = {
				"add": {
					"component_groups": [
						event_name
					]
				}
			}
        entity["minecraft:entity"]["events"][event_name] = event


    #Add event component groups (from event names)
    for i in range(len(event_names)):
        entity["minecraft:entity"]["component_groups"][event_names[i]] = {"minecraft:skin_id": {"value": i + 1}}


    #Add final "execute no event"
    entity["minecraft:entity"]["component_groups"]["echo:execute_no_command"] = {"minecraft:skin_id": {"value": 0}}

    #Add echo:despawn
    entity["minecraft:entity"]["component_groups"]["echo:despawn"] = {"minecraft:instant_despawn": {}}

    ##### HANDLE RANDOMIZERS
    randomizers = template.get("randomizers", {})
    for key in randomizers.keys():
        random_event_json = { "randomize": []}
        for e in randomizers.get(key).keys():
            random_event_json.get("randomize").append({ "weight": randomizers.get(key).get(e), "add": { "component_groups": [ e ] }})
        entity["minecraft:entity"]["events"]["echo:" + key] = random_event_json

    ##NOW DO THE ANIMATION CONTROLLER

    #Add default state
    default_state = {
					    "transitions": []
                    }

    for i in range(len(event_names)):
        event_n = event_names[i].replace(":","_")

        default_state["transitions"].append({
							event_n: "query.skin_id == " + str(i + 1)
						})
                        
    anim_controller["animation_controllers"][controller_name]["states"]["default"] = default_state

    # Add the on_death stuff
    if on_death := template.get("on_death", False):
        default_state["transitions"].append({
                        "on_death": "query.is_alive == 0"
                    })
        anim_controller["animation_controllers"][controller_name]["states"]["on_death"] = {"on_entry": on_death}

    # Add the rest of the states
    for i in range(len(event_names)):
        event_n = event_names[i].replace(":","_")

        comms = event_commands[i]
        com = {
					"transitions": [
						{
							"default": "query.skin_id != " + str(i + 1)
						}
					],
					"on_entry": comms
				}
        anim_controller["animation_controllers"][controller_name]["states"][event_n] = com

    #Save data to new files
    try:
        json.dump(entity, new_entity_file, indent=4, ensure_ascii=False)
        json.dump(anim_controller, new_anim_controller_file, indent=4, ensure_ascii=False)
    except Exception:
        error("Failed to save file.")
        err("This might be a permission issue.")
        err("entity and animation controllers will be missing or blank.")
        return debug_traceback()

    message("Entity successfully created with " + str(len(event_names)) + " states.\n", watch=True)
    if(len(event_names) > fetch_setting("max_allowed_states", store)):
        warning("Number of events exceeds allowed")
        warn("You may experience performance issues.")
        warn("Set `max_allowed_states` to configure when you see this message.")

# Loop through folders
def handle_folder_recursive(loc):
    for file in os.listdir(loc):
        new_loc = os.path.join(loc, file)
        if(os.path.isdir(new_loc)):
            handle_folder_recursive(new_loc)
        else:
            message(Fore.BLUE +  "\n=-=-=-=-=-=-=-=-=-=-=" + Style.RESET_ALL)
            handle_file(new_loc)

    
# Program evaluation begins here
if __name__ == "__main__":
    message("\nWelcome to Echo:NPC version v." + str(VERSION), watch=True)
    
    #Init settings stuff
    # init_settings()

    # TODO allow setting template folder from settings
    try:
        handle_folder_recursive(os.path.join(get_echo_path(), "templates"))
    except Exception as e:
        error("Echo has suffered a fatal error.")
        err("Run with '-d' for more information.")
        debug_traceback()
