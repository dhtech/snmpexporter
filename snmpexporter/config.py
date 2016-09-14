import yaml


class Config(object):

  def __init__(self, config=''):
    self.config = yaml.safe_load(config)

  def get(self, *path):
    ret = self.config or dict()
    for element in path:
      ret = ret.get(element, None)
      if not ret:
        return None
    return ret
