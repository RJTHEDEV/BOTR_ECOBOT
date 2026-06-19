import ast
import os

def extract_commands(directory):
    commands = {}
    for filename in os.listdir(directory):
        if not filename.endswith(".py"):
            continue
        filepath = os.path.join(directory, filename)
        cog_name = filename[:-3].capitalize()
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except:
                continue
        
        cmds = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        func_name = ""
                        if isinstance(decorator.func, ast.Attribute):
                            func_name = decorator.func.attr
                        elif isinstance(decorator.func, ast.Name):
                            func_name = decorator.func.id
                        
                        if func_name in ["hybrid_command", "command", "hybrid_group", "group"]:
                            # Extract name and description
                            cmd_name = node.name
                            description = "No description"
                            for kw in decorator.keywords:
                                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                    cmd_name = kw.value.value
                                if kw.arg == "description" and isinstance(kw.value, ast.Constant):
                                    description = kw.value.value
                            cmds.append((cmd_name, description, func_name))
                            break
                        
                        # Subcommands (e.g., @group_name.command)
                        if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "command":
                            if isinstance(decorator.func.value, ast.Name):
                                parent_group = decorator.func.value.id
                                cmd_name = node.name
                                description = "No description"
                                for kw in decorator.keywords:
                                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                        cmd_name = kw.value.value
                                    if kw.arg == "description" and isinstance(kw.value, ast.Constant):
                                        description = kw.value.value
                                
                                # Strip _group if it's there
                                if parent_group.endswith("_group"):
                                    parent_group = parent_group[:-6]
                                
                                cmds.append((f"{parent_group} {cmd_name}", description, "subcommand"))
        
        if cmds:
            commands[cog_name] = cmds
            
    return commands

cmds = extract_commands("cogs")
with open("commands_list.txt", "w", encoding="utf-8") as f:
    for cog, c_list in sorted(cmds.items()):
        f.write(f"\n### {cog}\n")
        for name, desc, ctype in sorted(c_list):
            f.write(f"- /{name} - {desc}\n")

