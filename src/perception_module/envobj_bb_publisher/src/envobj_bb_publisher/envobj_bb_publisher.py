#!/usr/bin/env python3
from typing import Counter
import carla
import rospy
# import sys
import numpy as np
from popgri_msgs.msg import BBInfo
from popgri_msgs.msg import BBList
from popgri_msgs.msg import BBSingleInfo
class PerceptionModule_BB():
    def __init__(self, carla_world, role_name='ego_vehicle', radius=10):
        self.sensing_radius = radius # default ?????
        self.world = carla_world
        self.vehicle = None
        self.role_name = role_name
        self.find_ego_vehicle()
    # find ego vehicle
    # reference: 
    def find_ego_vehicle(self):
        for actor in self.world.get_actors():
            if actor.attributes.get('role_name') == self.role_name:
                self.vehicle = actor
                break

    def set_radius(self, new_radius):
        self.sensing_radius = new_radius
    def get_radius(self):
        return self.sensing_radius
    # determine if the bounding box contains the given point
    def boundingbox_within_range(self, box, self_loc):
        radius = self.sensing_radius
        box_loc = box.location
        trans = carla.Transform(carla.Location(0,0,0), carla.Rotation(0,0,0))
        # obtain a vector pointing from self_loc to box center in world space
        vec_from_self_to_box = box_loc - self_loc
        # project the z coordinate to the bottom of the box
        if box_loc.z - box.extent.z > self_loc.z:
            vec_from_self_to_box.z = box_loc.z - box.extent.z - self_loc.z
        # project z coordinate to the top of the box
        elif box_loc.z + box.extent.z < self_loc.z:
            vec_from_self_to_box.z = self_loc.z - (box_loc.z + box.extent.z)
        # project z coordinate to the same level as the vehicle
        else :
            vec_from_self_to_box.z = 0
        normalized_vec = vec_from_self_to_box/self.distance_between_points(vec_from_self_to_box, vec_from_self_to_box)
        # calculate the location which is 'radius' away from the vehicle along the vec
        tip_of_vec = normalized_vec*radius
        loc_of_vec = tip_of_vec + self_loc
        if box.contains(loc_of_vec, trans):
            return True
        return False
    def distance_between_points(self, p1, p2):
        return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)
    # TODO: return bounding box of environment objects within range
    # get city objects in terms of info on their bounding box
    # return:vertices location in world space
    def get_bb_global_ver_within_range(self, obj_type):
        # TODO: need to check validity of object type
        if self.vehicle == None:
            self.find_ego_vehicle()
            # rospy.loginfo("No ego vehicle.")
            return
        all_env_bbs = self.world.get_environment_objects(obj_type)
        vehicle = self.vehicle
        self_loc = vehicle.get_location()
        radius = self.sensing_radius
        filtered_obstacles = []
        for env_bb in all_env_bbs:
            # center of the bounding box in world space
            center_of_box = env_bb.bounding_box.location
            dist = np.sqrt((center_of_box.x - self_loc.x)**2 + (center_of_box.y-self_loc.y)**2 + (center_of_box.z-self_loc.z)**2)
            if dist <= radius:
                filtered_obstacles.append((env_bb.bounding_box.get_local_vertices(), env_bb.name, env_bb.id))
            elif self.boundingbox_within_range(env_bb.bounding_box, self_loc):
                filtered_obstacles.append((env_bb.bounding_box.get_local_vertices(), env_bb.name, env_bb.id))
        return filtered_obstacles

# publish obstacles and lane waypoints information
def publisher(percep_mod, label_list, role_name):
    # main function
    pub = rospy.Publisher('/carla/%s/environment_obj_bb'%role_name, BBList, queue_size=1)
    rate = rospy.Rate(10)
    while not rospy.is_shutdown():
        for label in label_list:
            # get all vertices of all bounding boxes which are within the radius with label 'label'
            vertices_of_cur_label = percep_mod.get_bb_global_ver_within_range(label)
            bbs_msgs = BBList()
            if not vertices_of_cur_label:
                continue
            for vertices_of_one_box in vertices_of_cur_label:
                info = BBInfo()
                for loc in vertices_of_one_box[0]:
                    vertex = BBSingleInfo()
                    vertex.vertex_location.x = loc.x
                    vertex.vertex_location.y = loc.y
                    vertex.vertex_location.z = loc.z
                    info.vertices_locations.append(vertex)
                info.type = str(label)
                info.name = str(vertices_of_one_box[1])
                info.id = vertices_of_one_box[2] % 1013 # NOTE 1013 is a magic number, the purpose is to shorten the id from a very large number
                bbs_msgs.bounding_box_vertices.append(info)
            pub.publish(bbs_msgs)
        rate.sleep()


if __name__ == "__main__":
    # reference: https://github.com/SIlvaMFPedro/ros_bridge/blob/master/carla_waypoint_publisher/src/carla_waypoint_publisher/carla_waypoint_publisher.py
    rospy.init_node('envobj_bb_publisher', anonymous=True)
    # host = rospy.get_param("/carla/host", "127.0.0.1")
    # port = rospy.get_param("/carla/host", 2000)
    # timeout = rospy.get_param("/carla/timeout", 10)
    client = carla.Client('localhost', 2000)
    role_name = rospy.get_param("~role_name", "ego_vehicle")
    # client.set_timeout(timeout)
    world = client.get_world()
    pm = PerceptionModule_BB(world, role_name=role_name)
    default_list = [carla.CityObjectLabel.Vehicles, carla.CityObjectLabel.Buildings, carla.CityObjectLabel.Fences, carla.CityObjectLabel.Pedestrians, carla.CityObjectLabel.Sidewalks, carla.CityObjectLabel.Walls, carla.CityObjectLabel.Vegetation, carla.CityObjectLabel.GuardRail]
    publisher(pm, default_list, role_name)