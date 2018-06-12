import os.path
import yaml


class YamlLoader(yaml.SafeLoader):

    def __init__(self, stream):
        self._root = os.path.dirname(stream.name)
        super(YamlLoader, self).__init__(stream)

    def include(self, node):
        filename = os.path.join(self._root, self.construct_scalar(node))
        with open(filename, 'r') as f:
            return yaml.load(f, YamlLoader)


YamlLoader.add_constructor('!include', YamlLoader.include)


def load(filename):
  with open(filename, 'r') as f:
    return yaml.load(f, YamlLoader)
