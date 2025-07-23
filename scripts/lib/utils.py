import yaml

def read_yaml_file(filename: str):
    with open(filename, 'r') as file:
        return yaml.safe_load(file.read())
