"""Simple demo maya plugin node.

Use the plugin manager to load this plugin.
Use this python command to load the plugin into your scene:

from maya import cmds
cmds.createNode('demoNode')
"""

from maya import cmds
from maya.api import OpenMaya

maya_useNewAPI = True

class demoNode(OpenMaya.MPxNode):
    """A very simple demo node."""
    # Maya provides the node ids from 
    # 0x00000000 to 0x0007ffff 
    # for users to customize.
    type_id = OpenMaya.MTypeId(0x00000000)
    type_name = "demoNode"

    # attributes
    input_one = None
    input_two = None
    output = None

    def __init__(self):
        OpenMaya.MPxNode.__init__(self)

    @classmethod
    def initialize(cls):
        """Create attributes and dependecies."""
        numeric_attr = OpenMaya.MFnNumericAttribute()

        cls.input_one = numeric_attr.create(
            'inputOne', # longname
            'io', # shortname
            OpenMaya.MFnNumericData.kFloat # attribute type
        )
        numeric_attr.readable = False
        numeric_attr.writable = True
        numeric_attr.keyable = True
        cls.addAttribute(cls.input_one)

        cls.input_two = numeric_attr.create(
            'inputTwo', # longname
            'it', # shortname
            OpenMaya.MFnNumericData.kFloat # attribute type
        )
        numeric_attr.readable = False
        numeric_attr.writable = True
        numeric_attr.keyable = True
        cls.addAttribute(cls.input_two)

        cls.output = numeric_attr.create(
            'output', # longname
            'o', # shortname
            OpenMaya.MFnNumericData.kFloat # attribute type
        )
        numeric_attr.readable = True
        numeric_attr.writable = False
        cls.addAttribute(cls.output)

        # attribute dependencies
        cls.attributeAffects( cls.input_one, cls.output )
        cls.attributeAffects( cls.input_two, cls.output )

    @classmethod
    def creator(cls):
        """Create class instance.

        Returns:
            demoNode: instance of this class.
        """
        return cls()
        
    def compute(self, plug, data_block):
        """Compute this node.
        
        Args:
            plug (MPlug):
                plug representing the attribute that needs to be recomputed.
            data_block (MDataBlock): 
                data block containing storage for the node's attributes.
        """

        if plug == self.output:
            # get data from inputs
            input_one = data_block.inputValue(self.input_one).asFloat()
            input_two = data_block.inputValue(self.input_two).asFloat()

            # get output handle, set its new value, and set it clean.
            output_handle = data_block.outputValue(self.output)
            output_handle.setFloat((input_one + input_two)/2.0)
            output_handle.setClean()


def initializePlugin(plugin):
    """Called when plugin is loaded.

    Args:
        plugin (MObject): The plugin.
    """
    plugin_fn = OpenMaya.MFnPlugin(plugin)

    try:
        plugin_fn.registerNode(
            demoNode.type_name,
            demoNode.type_id,
            demoNode.creator,
            demoNode.initialize,
            OpenMaya.MPxNode.kDependNode
        )
    except:
        print "failed to register node {0}".format(demoNode.type_name)
        raise


def uninitializePlugin(plugin):
    """Called when plugin is unloaded.

    Args:
        plugin (MObject): The plugin.
    """
    plugin_fn = OpenMaya.MFnPlugin(plugin)

    try:
        plugin_fn.deregisterNode(demoNode.type_id)
    except:
        print "failed to deregister node {0}".format(demoNode.type_name)
        raise
