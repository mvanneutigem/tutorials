"""mnCollisionDeformer.py.

Copyright (C) 2020  Marieke van Neutigem

This plugin was written for educational purposes, it was written with the intent 
of learning and educating about writing deformers for maya. 

To test this plugin in maya:
1. load the plugin using the plug-in manager.
2. Select the affected mesh and the collider, in that order.
3. Run this snippet in a python script editor tab:

------------------------------------snippet-------------------------------------
from maya import cmds
selection = cmds.ls(sl=True)
if len(selection) == 2:
    mesh = selection[0]
    collider_shapes = cmds.listRelatives(selection[1], shapes=True)
    cmds.select(mesh)
    deformer_nodes = cmds.deformer( type='mnCollisionDeformer' )
    cmds.connectAttr(
        '{0}.worldMesh'.format(collider_shapes[0]),
        '{0}.collider'.format(deformer_nodes[0]),
    )
else:
    print 'Failed to add mnCollisionDeformer, please select mesh and collider.'
----------------------------------end snippet-----------------------------------

Contact: mvn882@hotmail.com
https://mariekevanneutigem.nl/blog
"""
import math

# Use maya API 1.0 because MPxDeformerNode is not available in 2.0 yet.
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx
from maya.mel import eval as mel_eval


# set globals to the proper cpp cvars. (compatible from maya 2016)
kInput = OpenMayaMPx.cvar.MPxGeometryFilter_input
kInputGeom = OpenMayaMPx.cvar.MPxGeometryFilter_inputGeom
kOutputGeom = OpenMayaMPx.cvar.MPxGeometryFilter_outputGeom
kEnvelope = OpenMayaMPx.cvar.MPxGeometryFilter_envelope
kGroupId = OpenMayaMPx.cvar.MPxGeometryFilter_groupId

class mnCollisionDeformer(OpenMayaMPx.MPxDeformerNode):
    """Node to deform mesh on collision."""
    # replace this with a valid node id for use in production.
    type_id = OpenMaya.MTypeId(0x00001)  
    type_name = "mnCollisionDeformer"

    collider_attr = None
    bulge_attr = None
    levels_attr = None
    bulgeshape_attr = None

    @classmethod
    def initialize(cls):
        """Create attributes."""
        numeric_attr_fn = OpenMaya.MFnNumericAttribute()
        generic_attr_fn = OpenMaya.MFnGenericAttribute()
        ramp_attr_fn = OpenMaya.MRampAttribute()
        
        # Collider mesh as an input, this needs to be connected to the worldMesh 
        # output attribute on a given shape.
        cls.collider = generic_attr_fn.create(
            'collider', 
            'cl', 
        )
        generic_attr_fn.addDataAccept( OpenMaya.MFnData.kMesh )
        cls.addAttribute( cls.collider )

        # Multiplier for the amount of bulge to apply.
        cls.bulge_attr = numeric_attr_fn.create(
            'bulgeMultiplier',
            'bm',
            OpenMaya.MFnNumericData.kFloat
        )
        numeric_attr_fn.readable = False
        numeric_attr_fn.writable = True
        numeric_attr_fn.keyable = True
        cls.addAttribute(cls.bulge_attr)

        # Levels of vertices to apply the bulge to.
        cls.levels_attr = numeric_attr_fn.create(
            'levels',
            'l',
            OpenMaya.MFnNumericData.kInt
        )
        numeric_attr_fn.readable = False
        numeric_attr_fn.writable = True
        numeric_attr_fn.keyable = True
        cls.addAttribute(cls.levels_attr)

        # Shape of the bulge, as a ramp to be user directable.
        cls.bulgeshape_attr = ramp_attr_fn.createCurveRamp(
            "bulgeShape", 
            "bs"
        )
        cls.addAttribute(cls.bulgeshape_attr)
        
        # All inputs affect the output geometry.
        cls.attributeAffects( cls.bulgeshape_attr, kOutputGeom )
        cls.attributeAffects( cls.levels_attr, kOutputGeom )
        cls.attributeAffects( cls.bulge_attr, kOutputGeom )
        cls.attributeAffects( cls.collider, kOutputGeom )

    @classmethod
    def creator(cls):
        """Create instance of this class.

        Returns:
            mnCollisionDeformer: New class instance.
        """
        return cls()

    def __init__(self):
        """Construction."""
        OpenMayaMPx.MPxDeformerNode.__init__(self)

    def postConstructor(self):
        """This is called when the node has been added to the scene."""

        # Populate bulge shape ramp attribute with default values.
        node = self.thisMObject()
        bulgeshape_handle = OpenMaya.MRampAttribute(node, self.bulgeshape_attr)
        
        positions = OpenMaya.MFloatArray()
        values = OpenMaya.MFloatArray()
        interps = OpenMaya.MIntArray()
        
        positions.append(float(0.0))
        positions.append(float(1.0))
        
        values.append(float(0.0))
        values.append(float(0.0))
        
        interps.append(OpenMaya.MRampAttribute.kSpline)
        interps.append(OpenMaya.MRampAttribute.kSpline)
        
        bulgeshape_handle.addEntries(positions, values, interps)
        

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
        # The envelope determines the weight of the deformer on the mesh.
        envelope_attribute = kEnvelope
        envelope_value = data_block.inputValue( envelope_attribute ).asFloat()

        # Get the input mesh from the datablock using our 
        # getDeformerInputGeometry() helper function.     
        input_geometry_object = self.getDeformerInputGeometry(
            data_block, 
            geometry_index
        )

        # Get the collider mesh, abort if none is found.
        collider_handle = data_block.inputValue( self.collider )
        try:
            collider_object = collider_handle.asMesh()
            collider_fn = OpenMaya.MFnMesh(collider_object)
        except:
            return
        
        # Obtain the list of normals for each vertex in the mesh.
        normals = OpenMaya.MFloatVectorArray()
        mesh_fn = OpenMaya.MFnMesh( input_geometry_object )
        mesh_fn.getVertexNormals( True, normals, OpenMaya.MSpace.kTransform )

        # Store the original points of this mesh, if all points turn out to be
        # inside the collider we will want to use this to restore the original
        # points instead of using the overrides.
        orig_points = OpenMaya.MPointArray()
        mesh_fn.getPoints(orig_points)
        
        mesh_vertex_iterator = OpenMaya.MItMeshVertex(input_geometry_object)

        # Iterate over the vertices to move them.
        global vertexIncrement
        intersecting_indices = []
        neighbouring_indices = []

        inside_mesh = True
        # denting the mesh inwards along the collider.
        while not mesh_vertex_iterator.isDone():
            
            vertex_index = mesh_vertex_iterator.index()

            normal = OpenMaya.MVector( normals[vertex_index] ) 
            
            # Get the world space point/normal in float and non float values.
            point = mesh_vertex_iterator.position()
            ws_point = point * local_to_world_matrix
            ws_fl_point = OpenMaya.MFloatPoint(ws_point)

            ws_normal = normal * local_to_world_matrix
            # inverting the direction of the normal to make it point in the same
            # direction as the colliding mesh's normal.
            ws_fl_normal = OpenMaya.MFloatVector(ws_normal) * -1

            # Get the intersection for this point/normal combination.
            intersecting_point = self.getIntersection(
                ws_fl_point, 
                ws_fl_normal, 
                collider_fn
            )

            # if no intersecting point is found skip it.
            if intersecting_point:
                # get the vector from the intersecting point to the 
                # original point
                diff = intersecting_point - ws_fl_point

                # transform the vector to local space, and multiply it using
                # the given envelope value to determine the influence.
                new_point = point + OpenMaya.MVector( 
                    diff * envelope_value 
                ) * local_to_world_matrix.inverse()

                # get connected vertices of this vertex, store them in the 
                # neighbouring indices list to use later on to create the 
                # outwards bulging.
                verts = OpenMaya.MIntArray()
                mesh_vertex_iterator.getConnectedVertices(verts)
                for i in range(verts.length()):
                    neighbouring_indices.append(verts[i])

                # Set the position of the current vertex to the new point.
                mesh_vertex_iterator.setPosition( new_point )

                # store this point as an intersecting index.
                intersecting_indices.append(vertex_index)
            else:
                inside_mesh = False
            
            # Jump to the next vertex.
            mesh_vertex_iterator.next()

        # get the bulge and levels values.
        bulge = data_block.inputValue(self.bulge_attr).asFloat()
        levels = data_block.inputValue(self.levels_attr).asInt()
        if inside_mesh:
            mesh_fn.setPoints(orig_points)
        elif levels and bulge:
            # dent the mesh outward according to user input variables.
            bulgeshape_handle = OpenMaya.MRampAttribute(
                self.thisMObject(), 
                self.bulgeshape_attr
            )
            # get the list of neighbourhing indices that arent part of the 
            # intersecting indices. These will be used to identify what vertices 
            # to bulge outwards.
            outer_neighbour_indices = list(
                set(neighbouring_indices) - set(intersecting_indices)
            )
            multiplier = bulge * envelope_value

            # This is a recrusive method and will continue on for a given amount
            # of "levels" of depth.
            self.deformNeighbours(
                mesh_vertex_iterator,
                local_to_world_matrix,
                normals,
                intersecting_indices,
                outer_neighbour_indices,
                collider_fn,
                bulgeshape_handle,
                levels,
                multiplier,
                levels
            )

    def deformNeighbours(
        self, 
        mesh_vertex_iterator, 
        local_to_world_matrix,
        normals,
        past_indices, 
        indices, 
        collider_fn,
        bulgeshape_handle = None,
        levels = 1,
        multiplier = 1.0,
        max_levels = 1
    ):
        """Deform the given indices using given arguments.

        This is a recursive method, it will continue to find neighbouring 
        indices and execute this method on them for a given amount of levels.

        Due to this the mesh density has a big influence on the way the out 
        dent is shaped, it will likely be more performant to replace this logic 
        by using distance based rather than neighbourhing logic though this will 
        affect the look of the bulge.

        Args:
            mesh_vertex_iterator (MItMeshVertex): mesh iterator for the original 
                geometry, passed by reference so changes made to this will 
                be reflected live.
            local_to_world_matrix (MMatrix): transformation matrix to transform 
                given mesh vertex iterator data to world space.
            normals (MFloatVectorArray): array of normals by index.
            past_indices (list): indices to skip over, used to calculate new 
                list of indices for recurisve logic.
            indices (list): list of indices to apply the deformation to.
            collider_fn (MFnMesh): mesh of the object the mesh vertices are 
                colliding with.
            bulgeshape_handle (MDataHandle): handle of the bulgeshape ramp.
            levels (int): current number of levels of recursion, also used as to 
                map the value from the bulgeshape ramp.
            mutliplier (float): value to multiply strength of deformation with.
            max_levels(int): total number of recursions.
        """

        # Calculate the amount to bulge this layer of vertices.
        bulge_amount = None
        if bulgeshape_handle:
            # get the value for the current level from the ramp.
            bulgeshape_util = OpenMaya.MScriptUtil()
            bulgeshape = bulgeshape_util.asFloatPtr()
            try:
                bulgeshape_handle.getValueAtPosition(
                    float(levels)/float(max_levels), 
                    bulgeshape
                )
            except:
                bulgeshape = None
            if bulgeshape:
                bulge_amount = OpenMaya.MScriptUtil().getFloat(bulgeshape)

        # If it failed to get current bulge amount from ramp then fall back to 
        # an exponential curve.
        if not bulge_amount:
            bulge_amount = math.pow(levels, 2) / max_levels

        # Iterate all indices and apply the deformation.
        neighbouring_indices = []
        for i in indices:
            # throwaway script util because setIndex needs an int pointer.
            util = OpenMaya.MScriptUtil()
            prev_index = util.asIntPtr()
            mesh_vertex_iterator.setIndex(i, prev_index)

            # Get the world space point/normal in float and non float values.
            point = mesh_vertex_iterator.position()
            ws_point = point * local_to_world_matrix
            ws_fl_point = OpenMaya.MFloatPoint(ws_point)

            normal = OpenMaya.MVector( normals[i] ) 
            ws_normal = normal * local_to_world_matrix
            ws_fl_normal = OpenMaya.MFloatVector(ws_normal)

            # Get the closest intersection along the normal.
            intersections = OpenMaya.MFloatPointArray()
            collider_fn.allIntersections(
                ws_fl_point, ws_fl_normal, None, None, False, OpenMaya.MSpace.kWorld,
                1000, False, None, True, intersections, None,
                None, None, None, None
            )
            # Get the closest point by relying on the ordered array.
            intersecting_point = None
            if intersections.length() > 0:
                intersecting_point = intersections[0]

            # calculate the offset vector to add to the point.
            offset_vector = normal * multiplier * bulge_amount

            # Cap the length of the bulge to prevent the bulge from clipping 
            # through the collider.
            if intersecting_point:
                diff = OpenMaya.MVector( intersecting_point - ws_fl_point )
                if diff.length() < offset_vector.length():
                    offset_vector = diff * local_to_world_matrix.inverse()

            # calculate and set position of deformed point.
            new_point = point + offset_vector 
            mesh_vertex_iterator.setPosition( new_point )

            # get connected vertices of this vertex, store them in the 
            # neighbouring indices list to use later on to create the 
            # outwards bulging.
            verts = OpenMaya.MIntArray()
            mesh_vertex_iterator.getConnectedVertices(verts)
            for i in range(verts.length()):
                neighbouring_indices.append(verts[i])

        # If the current level is not 0, continue recursion.
        levels = levels - 1
        if levels > 0:
            # get the list of neighbourhing indices that arent part of the 
            # past indices. These will be used to identify what vertices 
            # to bulge outwards next.
            past_indices.extend(indices)
            new_indices = list(
                set(neighbouring_indices) - set(past_indices)
            )
            self.deformNeighbours(
                mesh_vertex_iterator, 
                local_to_world_matrix,
                normals,
                past_indices, 
                new_indices, 
                collider_fn,
                bulgeshape_handle,
                levels,
                multiplier,
                max_levels
            )


    def getIntersection(self, point, normal, mesh):
        """Check if given point is inside given mesh.
        
        Args:
            point (MFloatPoint): point to check if inside mesh.
            normal (MFloatVector): normal of given point.
            mesh (MFnMesh): mesh to check if point inside.

        Returns:
            MPoint, MNormal
        """
        intersection_normal = OpenMaya.MVector()
        closest_point = OpenMaya.MPoint()

        # Get closest point/normal to given point in normal direction on mesh.
        mesh.getClosestPointAndNormal(
            OpenMaya.MPoint(point),
            closest_point,
            intersection_normal,
            OpenMaya.MSpace.kWorld,
        )
        
        # if the the found normal on the mesh is in a direction opposite to the 
        # given normal, fall back to given normal, else use the average normal.
        # This is to get a more even vertex distribution on the new mesh.
        angle = normal.angle(OpenMaya.MFloatVector(intersection_normal))
        if angle >= math.pi or angle <= -math.pi:
            average_normal = normal
        else:
            average_normal = OpenMaya.MVector(normal) + intersection_normal

        # Find intersection in direction determined above.
        intersections = OpenMaya.MFloatPointArray()
        mesh.allIntersections(
            point, OpenMaya.MFloatVector(average_normal), None, None, False, OpenMaya.MSpace.kWorld,
            1000, False, None, True, intersections, None,
            None, None, None, None
        )

        # If number of intersections is even then the given point is not inside
        # the mesh. The intersections are ordered so return the first one found
        # as that is the closest one.
        intersecting_point = None
        if intersections.length()%2 == 1:
            intersecting_point = intersections[0]
        
        return intersecting_point


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
    plugin_fn = OpenMayaMPx.MFnPlugin(plugin, "Marieke van Neutigem", "0.0.1")

    try:
        plugin_fn.registerNode(
            mnCollisionDeformer.type_name,
            mnCollisionDeformer.type_id,
            mnCollisionDeformer.creator,
            mnCollisionDeformer.initialize,
            OpenMayaMPx.MPxNode.kDeformerNode
        )
    except:
        print "failed to register node {0}".format(mnCollisionDeformer.type_name)
        raise

    # Load custom Attribute Editor GUI.
    mel_eval( gui_template )


def uninitializePlugin(plugin):
    """Called when plugin is unloaded.

    Args:
        plugin (MObject): The plugin.
    """
    plugin_fn = OpenMayaMPx.MFnPlugin(plugin)

    try:
        plugin_fn.deregisterNode(mnCollisionDeformer.type_id)
    except:
        print "failed to deregister node {0}".format(
            mnCollisionDeformer.type_name
        )
        raise


#  Custom attribute editor gui template
gui_template = '''
    global proc AEmnCollisionDeformerTemplate( string $nodeName )
    {
        editorTemplate -beginScrollLayout;
            // Add attributes to show in attribute editor.
            editorTemplate -beginLayout "Collision Deformer Attributes" -collapse 0;
                editorTemplate -addSeparator;
                editorTemplate -addControl  "collider" ;
                editorTemplate -addControl  "levels" ;
                editorTemplate -addControl  "bulgeMultiplier" ;
                editorTemplate -addControl  "envelope" ;
                AEaddRampControl "bulgeShape" ;
            editorTemplate -endLayout;
            // Add base node attributes
            AEdependNodeTemplate $nodeName;
            // Add extra atttributes
            editorTemplate -addExtraControls;
        editorTemplate -endScrollLayout;
    }
'''
