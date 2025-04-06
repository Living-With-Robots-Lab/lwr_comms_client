** This github repo is a ros2 humble package **

## How to setup lwr comms client?
```
cd [YOUR_ROS2_ws]/src
git clone https://github.com/Living-With-Robots-Lab/lwr_comms_client.git
```

open the 'robot_config.yaml' to setup the robot:
```
robot_name: "<YOUR ROBOT'S NAME.>" # Examples: bender, flexo, dobby, etc
server_uri: "ws://10.2.0.60:8080" # Your server's Wireguard IP address provided by the AMRL group.
```

```
publish_topics:
  - name: "/cmd_vel"
    type: "geometry_msgs.msg.Twist"
```
publish_topics: This setup on the client will subscribe to '/cmd_vel' published by your robot and then will send the data to the server so that other robots can subscribe to it on '/[YOUR_ROBOT_NAME]/cmd_vel'. 

Example if your robot's name is 'bender' then the client will send '/bender/cmd_vel' to the server and will distribute that to whoever requests that topic.

```
subscribe_topics:
  - name: "/flexo/cmd_vel"
    type: "geometry_msgs.msg.Twist"
```
subscribe_topics: This will let the client subscribe to '/cmd_vel' topic from the 'flexo' robot.

You can publish and subscribe to multiple topics to and from the server. Keep adding '-name' and 'type' to the publish and subscribe topics list.
