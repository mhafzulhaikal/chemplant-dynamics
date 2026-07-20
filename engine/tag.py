# engine/tag.py


class Tag:
    def __init__(self, name, tag_type):
        self.name = name
        self.type = tag_type  # PV, SP, MV

    def __repr__(self):
        return f'<Tag {self.name} ({self.type})>'
