import copy
import os
from threading import Lock

import rospy
import rospkg
from qt_gui.plugin import Plugin
from python_qt_binding import QtCore
from python_qt_binding import loadUi
from python_qt_binding.QtWidgets import QWidget
from sensor_msgs.msg import Joy


class JoyMonitor(Plugin):
    def __init__(self, context):
        super(JoyMonitor, self).__init__(context)

        self.lock = Lock()

        # Give QObjects reasonable names
        self.setObjectName('JoyMonitor')

        # Process standalone plugin command-line arguments
        from argparse import ArgumentParser
        parser = ArgumentParser()
        # Add argument(s) to the parser.
        parser.add_argument("-q", "--quiet", action="store_true",
                            dest="quiet",
                            help="Put plugin in silent mode")
        parser.add_argument("-t", "--topic",
                            dest="topic",
                            type=str,
                            help="Set topic to publish [default:/joy]",
                            default="/joy")
        parser.add_argument("-r", "--rate",
                            dest="rate",
                            type=float,
                            help="Set publish rate [default:20]",
                            default=20)

        args, unknowns = parser.parse_known_args(context.argv())
        if not args.quiet:
            print('arguments: ' + str(args))
            print('unknowns: ' + str(unknowns))

        # Create QWidget
        self._widget = QWidget()
        # Get path to UI file which should be in the "resource" folder of this package
        ui_file = os.path.join(rospkg.RosPack().get_path('rqt_virtual_joy'), 'resource', 'VirtualJoy.ui')
        # Extend the widget with all attributes and children from UI file
        loadUi(ui_file, self._widget)
        # Give QObjects reasonable names
        self._widget.setObjectName('JoyMonitorUi')
        # Show _widget.windowTitle on left-top of each plugin (when
        # it's set in _widget). This is useful when you open multiple
        # plugins at once. Also if you open multiple instances of your
        # plugin at once, these lines add number to make it easy to
        # tell from pane to pane.
        if context.serial_number() > 1:
            self._widget.setWindowTitle(self._widget.windowTitle() + (' (%d)' % context.serial_number()))
        # Add widget to the user interface
        context.add_widget(self._widget)

        self._widget.topicLineEdit.returnPressed.connect(self.topicNameUpdated)
        self._widget.topicLineEdit.setText(args.topic)  # Default Topic
        self.updateSubscriber()

        self._widget.publishCheckBox.hide()
        self._widget.rateSpinBox.hide()

        self._widget.shapeSelectBox.hide()
        self._widget.joy.setMode("square")

    def topicNameUpdated(self):
        self.updateSubscriber()

    def updateSubscriber(self):
        topic = str(self._widget.topicLineEdit.text())
        try:
            if self.sub is not None:
                self.sub.unregister()
        except Exception:
            pass
        self.sub = None
        self.joy_msg = Joy()
        rospy.loginfo(f"subscribing to {topic}")
        self.sub = rospy.Subscriber(topic, Joy, self.joy_callback, queue_size=10)

        rate = self._widget.rateSpinBox.value()
        self.startIntervalTimer(int(1000.0 / rate))

    def joy_callback(self, joy_msg):
        with self.lock:
            self.joy_msg = joy_msg

    def startIntervalTimer(self, msec):
        try:
            self._timer.stop()
        except Exception:
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self.processTimerShot)

        if msec > 0:
            self._timer.setInterval(msec)
            self._timer.start()

    def updateJoyPosLabel(self):
        pos = self.getROSJoyValue()
        text = "({:1.2f},{:1.2f})".format(pos['x'], pos['y'])
        self._widget.joyPosLabel.setText(text)

    def processTimerShot(self):
        with self.lock:
            joy_msg = copy.deepcopy(self.joy_msg)

        num_axes = len(joy_msg.axes)
        num_buttons = len(joy_msg.buttons)

        if num_axes >= 2:
            x = joy_msg.axes[0]
            y = joy_msg.axes[1]
            self._widget.joy._stickView.move_joy(x, y)

        # TODO(lucasw) this method is ugly, should make buttons into a list on init
        for i in range(num_buttons):
            try:
                eval("self._widget.button" + str(i + 1)).setDown(joy_msg.buttons[i])
            except (AttributeError, IndexError):  # as ex:
                # rospy.logwarn_throttle(1.0, ex)
                break

    def shutdown_plugin(self):
        self.sub.unregister()
        pass

    def save_settings(self, plugin_settings, instance_settings):
        # TODO save intrinsic configuration, usually using:
        # instance_settings.set_value(k, v)
        pass

    def restore_settings(self, plugin_settings, instance_settings):
        # TODO restore intrinsic configuration, usually using:
        # v = instance_settings.value(k)
        pass

    # def trigger_configuration(self):
        # Comment in to signal that the plugin has a way to configure
        # This will enable a setting button (gear icon) in each dock widget title bar
        # Usually used to open a modal configuration dialog
