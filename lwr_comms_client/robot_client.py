import asyncio
import websockets
import json
import yaml
import rclpy
from rclpy.node import Node
from rclpy.serialization import serialize_message, deserialize_message
import base64
import threading
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
import importlib
# QoS profile for ROS 2 message reliability
qos_profile = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10
)

ws_connection = None
ws_loop = None

async def ws_client(uri, config):
    """WebSocket client that maintains connection with the server."""
    global ws_connection
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                ws_connection = websocket
                reg_msg = {
                    "robot_name": config.get("robot_name"),
                    "publish_topics": config.get("publish_topics", []),
                    "subscribe_topics": config.get("subscribe_topics", [])
                }
                await websocket.send(json.dumps(reg_msg))

                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        print("brother?")
                        handle_server_message(data)
                    except websockets.ConnectionClosed:
                        print("WebSocket connection lost, attempting to reconnect...")
                        break  # Break inner loop to reconnect
        except Exception as e:
            print(f"WebSocket connection error: {e}, retrying in 5 seconds...")
            await asyncio.sleep(5)  # Wait before reconnecting

def handle_server_message(data):
    """Processes incoming messages from the WebSocket server."""
    topic = data.get("topic")
    encoded_msg = data.get("data")
    
    # print(f"Received message from WebSocket: {data}")  # Debugging print

    if topic and encoded_msg:
        if topic in RobotClient.subscribers:
            serialized_msg = base64.b64decode(encoded_msg)
            msg_type = RobotClient.subscribers[topic]["msg_type"]
            msg = deserialize_message(serialized_msg, msg_type)
            # print(f"Publishing on {topic}: {msg}")  # Debugging print
            RobotClient.subscribers[topic]["publisher"].publish(msg)

# def send_message_to_server(topic, data):
#     """Sends a message to the WebSocket server asynchronously."""
#     global ws_loop, ws_connection
#     if ws_connection and ws_connection.open:
#         async def send():
#             payload = {"topic": topic, "data": data}
#             try:
#                 # print("sending data")
#                 await ws_connection.send(json.dumps(payload))
#             except Exception as e:
#                 print(f"Error sending message: {e}")
        
#         asyncio.run_coroutine_threadsafe(send(), ws_loop)

async def reconnect_websocket():
    global ws_connection
    print("[Client] Reconnecting to WebSocket...")
    try:
        ws_connection = await websockets.connect("ws://your_server_address")
        print("[Client] Reconnected successfully.")
    except Exception as e:
        print(f"[Client] Reconnection failed: {e}")
        await asyncio.sleep(5)  # Wait before retrying
        await reconnect_websocket()  # Try again

async def send_message_to_server(topic, data):
    global ws_connection  
    try:
        if ws_connection and ws_connection.state == websockets.protocol.State.OPEN:
            payload = json.dumps({"topic": topic, "data": data})
            await ws_connection.send(payload)  # Use await here
        else:
            print("[Client] WebSocket connection is closed. Reconnecting...")
            await reconnect_websocket()
    except Exception as e:
        print(f"[Client] Failed to send message: {e}")
        await reconnect_websocket()

def start_ws_client(config):
    """Starts the WebSocket client in a separate event loop."""
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    server_uri = config.get("server_uri", "ws://10.2.0.60:8080")
    ws_loop.run_until_complete(ws_client(server_uri, config))

class RobotClient(Node):
    subscribers = {}

    def __init__(self, config):
        super().__init__('robot_client')
        self.robot_name = config.get("robot_name")
        self.publish_topics = config.get("publish_topics", [])
        self.subscribe_topics = config.get("subscribe_topics", [])
        self.subscribers = {}  # Instance variable for subscriber management

        self.get_logger().info(f"Robot '{self.robot_name}' started. Publishing: {self.publish_topics}, Subscribing: {self.subscribe_topics}")

        # Set up publishing
        for topic_info in self.publish_topics:
            topic_name = topic_info["name"]
            msg_type = self.get_msg_type(topic_info["type"])
            if msg_type:
                self.create_subscription(msg_type, topic_name, self.get_message_callback(topic_name), qos_profile)
                self.get_logger().info(f"Publishing topic: {topic_name}")

        # Set up subscriptions
        for topic_info in self.subscribe_topics:
            topic_name = topic_info["name"]
            msg_type = self.get_msg_type(topic_info["type"])
            if msg_type:
                publisher = self.create_publisher(msg_type, topic_name, qos_profile)
                self.subscribers[topic_name] = {"publisher": publisher, "msg_type": msg_type}
                self.get_logger().info(f"Subscribed to topic: {topic_name}")

    def get_msg_type(self, msg_type_str):
        """Dynamically imports the correct message type."""
        try:
            module_name, class_name = msg_type_str.rsplit(".", 1)
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except Exception as e:
            self.get_logger().error(f"Failed to import message type '{msg_type_str}': {e}")
            return None                

    def get_message_callback(self, topic):
        """Returns a callback function for publishing messages to WebSocket."""
        def callback(msg):
            serialized = serialize_message(msg)
            encoded_msg = base64.b64encode(serialized).decode('utf-8')
            msg_type = f"{msg.__class__.__module__}.{msg.__class__.__name__}"
            data = {"msg_type": msg_type, "message": encoded_msg}
            send_message_to_server(topic, data)
        return callback

def main(args=None):
    """Main function to start the ROS 2 node and WebSocket client."""
    with open("/home/bwidemo/bwi_ros2/src/lwr_comms_client/configs/robot_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Start WebSocket client in a separate thread
    ws_thread = threading.Thread(target=start_ws_client, args=(config,))
    ws_thread.daemon = True
    ws_thread.start()

    # Initialize ROS 2 node
    rclpy.init(args=args)
    robot_node = RobotClient(config)

    try:
        rclpy.spin(robot_node)
    except KeyboardInterrupt:
        pass
    finally:
        robot_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
