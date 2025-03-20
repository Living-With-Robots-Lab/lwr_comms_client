from setuptools import find_packages, setup

package_name = 'lwr_comms_client'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'websockets', 'pyyaml'],
    zip_safe=True,
    maintainer='bwidemo',
    maintainer_email='nikunjparmar828@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'robot_client = lwr_comms_client.robot_client:main'
        ],
    },
)
