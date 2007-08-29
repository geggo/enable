""" Defines the TraitsTool and Fifo classes, and get_nested_components90
function.
"""
# Enthought library imports
from enthought.enable2.api import BaseTool, Container
from enthought.traits.api import Any, Dict, Enum, Float, Instance
from enthought.traits.ui.api import View



class Fifo:
    """ Slightly-modified version of the Fifo class from the Python cookbook:
        http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/68436
    """
    def __init__(self):
        self.nextin = 0
        self.nextout = 0
        self.data = {}
    def append(self, value):
        self.data[self.nextin] = value
        self.nextin += 1
    def extend(self, values):
        if len(values) > 0:
            for i,val in enumerate(values):
                self.data[i+self.nextin] = val
            self.nextin += i+1
    def isempty(self):
        return self.nextout >= self.nextin
    def pop(self):
        value = self.data[self.nextout]
        del self.data[self.nextout]
        self.nextout += 1
        return value


def get_nested_components(container):
    """ Returns a list of fundamental plotting components from a container
    with nested containers.  
    
    Performs a breadth-first search of the containment hierarchy. Each element
    in the returned list is a tuple (component, (x,y)) where (x,y) is the 
    coordinate frame offset of the component from the top-level container.
    """
    components = []
    worklist = Fifo()
    worklist.append((container, (0,0)))
    while 1:
        item, offset = worklist.pop()
        if isinstance(item, Container):
            new_offset = (offset[0]+item.x, offset[1]+item.y)
            for c in item.components:
                worklist.append((c, new_offset))
        if worklist.isempty():
            break
    return components


class TraitsTool(BaseTool):
    """ Tool to edit the traits of whatever Enable component happens
    to be clicked.  Handles containers and canvases so that they
    get edited only if their background regions are clicked.
    """
    
    # This tool does not have a visual representation (overrides BaseTool).
    draw_mode = "none"
    # This tool is not visible (overrides BaseTool).
    visible = False
    
    
    def normal_left_dclick(self, event):
        """ Handles the left mouse button being double-clicked when the tool
        is in the 'normal' state.
        
        If the event occurred on this tool's component (or any contained 
        component of that component), the method opens a Traits UI view on the
        component that was double-clicked, setting the tool as the active tool
        for the duration of the view.
        """
        x = event.x
        y = event.y

        # First determine what component or components we are going to hittest
        # on.  If our component is a container, then we add its non-container
        # components to the list of candidates.
        candidates = []
        component = self.component
        if isinstance(component, Container):
            candidates = get_nested_components(self.component)
        else:
            # We don't support clicking on unrecognized components
            return

        # Hittest against all the candidate and take the first one
        item = None
        for candidate, offset in candidates:
            if candidate.is_in(x-offset[0], y-offset[1]):
                item = candidate
                break

        if item:
            self.component.active_tool = self
            item.edit_traits(kind="livemodal")
            event.handled = True
            self.component.active_tool = None
            item.request_redraw()
        return
    


# EOF
