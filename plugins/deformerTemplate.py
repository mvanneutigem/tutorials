"""deformerTemplate.py.

Copyright (C) 2020  Marieke van Neutigem

This code was written for educational purposes, it was written with the intent 
of learning and educating about writing deformers for maya. 

Contact: mvn882@hotmail.com
https://mariekevanneutigem.nl/blog
"""

# You have to use maya API 1.0 because MPxDeformerNode is not available in 2.0.
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx
from maya.mel import eval as mel_eval


# Set globals to the proper cpp cvars. (compatible from maya 2016)
kInput = OpenMayaMPx.cvar.MPxGeometryFilter_input
kInputGeom = OpenMayaMPx.cvar.MPxGeometryFilter_inputGeom
kOutputGeom = OpenMayaMPx.cvar.MPxGeometryFilter_outputGeom
kEnvelope = OpenMayaMPx.cvar.MPxGeometryFilter_envelope
kGroupId = OpenMayaMPx.cvar.MPxGeometryFilter_groupId

class templateDeformer(OpenMayaMPx.MPxDeformerNode):
    """Template deformer node."""
    # Replace this with a valid node id for use in production.
    type_id = OpenMaya.MTypeId(0x00001)  
    type_name = "templateDeformer"

    # Add attribute variables here.

    @classmethod
    def initialize(cls):
        """Initialize attributes and dependencies."""
        # Add any input and outputs to the deformer here, also set up 
        # dependencies between the in and outputs. If you want to use another 
        # mesh as an input you can use an MFnGenericAttribute and add 
        # MFnData.kMesh with the addDataAccept method.
        pass

    @classmethod
    def creator(cls):
        """Create instance of this class.

        Returns:
            templateDeformer: New class instance.
        """
        return cls()

    def __init__(self):
        """Construction."""
        OpenMayaMPx.MPxDeformerNode.__init__(self)

    def deform(
        self, 
        data_block, 
        geometry_iterator, 
        local_to_world_matrix, 
        geometry_index
    ):
        """Deform each vertex using the geometry iterator.
        
        Args:
            data_block (MDataBlock): the node's datablock.
            geometry_iterator (MItGeometry): 
                iterator for the geometry being deformed.
            local_to_world_matrix (MMatrix): 
                the geometry's world space transformation matrix.
            geometry_index (int): 
                the index corresponding to the requested output geometry.
        """
        # This is where you can add your deformation logic.

        # you can access the mesh this deformer is applied to either through
        # the given geometry_iterator, or by using the getDeformerInputGeometry 
        # method below.

        # You can access all your defined attributes the way you would in any 
        # other plugin, you can access base deformer attributes like the 
        # envelope using the global variables like so:

        # envelope_attribute = kEnvelope
        # envelope_value = data_block.inputValue( envelope_attribute ).asFloat()

    def getDeformerInputGeometry(self, data_block, geometry_index):
        """Obtain a reference to the input mesh. 
        
        We use MDataBlock.outputArrayValue() to avoid having to recompute the 
        mesh and propagate this recomputation throughout the Dependency Graph.
        
        OpenMayaMPx.cvar.MPxGeometryFilter_input and 
        OpenMayaMPx.cvar.MPxGeometryFilter_inputGeom (Maya 2016) 
        are SWIG-generated variables which respectively contain references to 
        the deformer's 'input' attribute and 'inputGeom' attribute.

        Args:
            data_block (MDataBlock): the node's datablock.
            geometry_index (int): 
                the index corresponding to the requested output geometry.
        """
        inputAttribute = OpenMayaMPx.cvar.MPxGeometryFilter_input
        inputGeometryAttribute = OpenMayaMPx.cvar.MPxGeometryFilter_inputGeom
        
        inputHandle = data_block.outputArrayValue( inputAttribute )
        inputHandle.jumpToElement( geometry_index )
        inputGeometryObject = inputHandle.outputValue().child(
            inputGeometryAttribute
        ).asMesh()
        
        return inputGeometryObject


def initializePlugin(plugin):
    """Called when plugin is loaded.

    Args:
        plugin (MObject): The plugin.
    """
    plugin_fn = OpenMayaMPx.MFnPlugin(plugin)

    try:
        plugin_fn.registerNode(
            templateDeformer.type_name,
            templateDeformer.type_id,
            templateDeformer.creator,
            templateDeformer.initialize,
            OpenMayaMPx.MPxNode.kDeformerNode
        )
    except:
        print "failed to register node {0}".format(templateDeformer.type_name)
        raise

    # Load custom Attribute Editor GUI.
    mel_eval( gui_template )


def uninitializePlugin(plugin):
    """Called when plugin is unloaded.

    Args:
        plugin (MObject): The plugin.
    """
    plugin_fn = OpenMayaMPx.MFnPlugin(plugin, "Marieke van Neutigem", "0.0.1")

    try:
        plugin_fn.deregisterNode(templateDeformer.type_id)
    except:
        print "failed to deregister node {0}".format(
            templateDeformer.type_name
        )
        raise


# This is a custom attribute editor gui template, if you want to display your
# attributes in a specific way you can define that here. (this is mel code)
gui_template = '''
    global proc AEmntemplateDeformerTemplate( string $nodeName )
    {
        editorTemplate -beginScrollLayout;
            // Add attributes to show in attribute editor.
            editorTemplate -beginLayout "template Deformer Attributes" -collapse 0;
                // Add your own attributes here in the way you want them to be displayed.
            editorTemplate -endLayout;
            // Add base node attributes
            AEdependNodeTemplate $nodeName;
            // Add extra atttributes
            editorTemplate -addExtraControls;
        editorTemplate -endScrollLayout;
    }
'''
