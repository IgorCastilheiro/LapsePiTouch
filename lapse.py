# Lapse-Pi timelapse controller for Raspberry Pi
# This must run as root (sudo python lapse.py) due to framebuffer, etc.
#
# http://www.adafruit.com/products/998  (Raspberry Pi Model B)
# http://www.adafruit.com/products/1601 (PiTFT Mini Kit)
#
# Prerequisite tutorials: aside from the basic Raspbian setup and PiTFT setup
# http://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi
#
# lapse.py by David Hunt (dave@davidhunt.ie)
# based on cam.py by Phil Burgess / Paint Your Dragon for Adafruit Industries.
# BSD license, all text above must be included in any redistribution.

# import wiringpi2
import cPickle
import fnmatch
import os
# import signal
# import sys
import threading
from datetime import datetime, timedelta
from time import sleep

import pygame
from pygame.locals import *


# UI classes ---------------------------------------------------------------

# Icon is a very simple bitmap class, just associates a name and a pygame
# image (PNG loaded from icons directory) for each.
# There isn't a globally-declared fixed list of Icons.  Instead, the list
# is populated at runtime from the contents of the 'icons' directory.

class Icon:
    def __init__(self, name):
        self.name = name
        try:
            self.bitmap = pygame.image.load(os.path.join(iconPath, name + '.png'))
        except IOError:
            pass


# Button is a simple tappable screen region.  Each has:
#  - bounding rect ((X,Y,W,H) in pixels)
#  - optional background color and/or Icon (or None), always centered
#  - optional foreground Icon, always centered
#  - optional single callback function
#  - optional single value passed to callback
# Occasionally Buttons are used as a convenience for positioning Icons
# but the taps are ignored.  Stacking order is important; when Buttons
# overlap, lowest/first Button in list takes precedence when processing
# input, and highest/last Button is drawn atop prior Button(s).  This is
# used, for example, to center an Icon by creating a passive Button the
# width of the full screen, but with other buttons left or right that
# may take input precedence (e.g. the Effect labels & buttons).
# After Icons are loaded at runtime, a pass is made through the global
# buttons[] list to assign the Icon objects (from names) to each Button.

class Button:
    def __init__(self, rect, **kwargs):
        self.rect = rect  # Bounds
        self.color = None  # Background fill color, if any
        self.iconBg = None  # Background Icon (atop color fill)
        self.iconFg = None  # Foreground Icon (atop background)
        self.bg = None  # Background Icon name
        self.fg = None  # Foreground Icon name
        self.callback = None  # Callback function
        self.value = None  # Value passed to callback
        for key, value in kwargs.iteritems():
            if key == 'color':
                self.color = value
            elif key == 'bg':
                self.bg = value
            elif key == 'fg':
                self.fg = value
            elif key == 'cb':
                self.callback = value
            elif key == 'value':
                self.value = value

    def selected(self, position):
        x1 = self.rect[0]
        y1 = self.rect[1]
        x2 = x1 + self.rect[2] - 1
        y2 = y1 + self.rect[3] - 1
        if ((position[0] >= x1) and (position[0] <= x2) and
                (position[1] >= y1) and (position[1] <= y2)):
            if self.callback:
                if self.value is None:
                    self.callback()
                else:
                    self.callback(self.value)
            return True
        return False

    def draw(self, current_screen):
        if self.color:
            current_screen.fill(self.color, self.rect)
        if self.iconBg:
            current_screen.blit(self.iconBg.bitmap,
                        (self.rect[0] + (self.rect[2] - self.iconBg.bitmap.get_width()) / 2,
                         self.rect[1] + (self.rect[3] - self.iconBg.bitmap.get_height()) / 2))
        if self.iconFg:
            current_screen.blit(self.iconFg.bitmap,
                        (self.rect[0] + (self.rect[2] - self.iconFg.bitmap.get_width()) / 2,
                         self.rect[1] + (self.rect[3] - self.iconFg.bitmap.get_height()) / 2))

    def set_bg(self, name):
        if name is None:
            self.iconBg = None
        else:
            for button_icon in icons:
                if name == button_icon.name:
                    self.iconBg = button_icon
                    break


# UI callbacks -------------------------------------------------------------
# These are defined before globals because they're referenced by items in
# the global buttons[] list.

# def motorCallback(n): # Pass 1 (next setting) or -1 (prev setting)
# 	global screenMode
# 	global motorRunning
# 	global motorDirection
# 	global motorpin
# 	global motorpinA
# 	global motorpinB
#
# 	if n == 1:
# 		motorDirection = 1
# 		motorpin = motorpinA
# 		if motorRunning == 0:
# 			motorRunning = 1
# 			gpio.digitalWrite(motorpin,gpio.HIGH)
# 		else:
# 			motorRunning = 0
# 			gpio.digitalWrite(motorpinA,gpio.LOW)
# 			gpio.digitalWrite(motorpinB,gpio.LOW)
# 	elif n == 2:
# 		motorDirection = 0
# 		motorpin = motorpinB
# 		if motorRunning == 0:
# 			motorRunning = 1
# 			gpio.digitalWrite(motorpin,gpio.HIGH)
# 		else:
# 			motorRunning = 0
# 			gpio.digitalWrite(motorpinA,gpio.LOW)
# 			gpio.digitalWrite(motorpinB,gpio.LOW)

def numeric_callback(n):  # Pass 1 (next setting) or -1 (prev setting)
    global screenMode
    global numberString
    global numeric
    if n < 10:
        numberString += str(n)
    elif n == 10:
        numberString = numberString[:-1]
    elif n == 11:
        screenMode = 1
    elif n == 12:
        screenMode = returnScreen
        numeric = int(numberString)
        v[dict_idx] = numeric


def setting_callback(n):  # Pass 1 (next setting) or -1 (prev setting)
    global screenMode
    screenMode += n
    if screenMode < 1:
        screenMode = len(buttons) - 1
    elif screenMode >= len(buttons):
        screenMode = 1


def values_callback(n):  # Pass 1 (next setting) or -1 (prev setting)
    global screenMode
    global returnScreen
    global numberString
    global numeric
    global v
    global dict_idx

    if n == -1:
        screenMode = 0
        save_settings()
    if n == 1:
        dict_idx = 'Pulse'
        numberString = str(v[dict_idx])
        screenMode = 2
        returnScreen = 1
    elif n == 2:
        dict_idx = 'Interval'
        numberString = str(v[dict_idx])
        screenMode = 2
        returnScreen = 1
    elif n == 3:
        dict_idx = 'Images'
        numberString = str(v[dict_idx])
        screenMode = 2
        returnScreen = 1


def view_callback(n):  # Viewfinder buttons
    global screenMode, screenModePrior
    if n is 0:  # Gear icon
        screenMode = 1


def done_callback():  # Exit settings
    global screenMode
    if screenMode > 0:
        save_settings()
    screenMode = 0  # Switch back to main window


def start_callback(n):  # start/Stop the timelapse thread
    global t, busy, threadExited
    global currentframe
    if n == 1:
        if busy:
            if threadExited:
                # Re-instanciate the object for the next start
                t = threading.Thread(target=time_lapse)
                threadExited = False
            t.start()
    if n == 0:
        if busy:
            busy = False
            t.join()
            currentframe = 0
            # Re-instanciate the object for the next time around.
            t = threading.Thread(target=time_lapse)


def time_lapse():
    global v
    global settling_time
    # global shutter_length
    # global motorpin
    # global shutterpin
    # global backlightpin
    global busy, threadExited
    global currentframe

    busy = True

    photos_dir = os.path.join("/home/pi/LapsePiTouch/", datetime.now().strftime('%Y-%m-%d\ %H:%M'))
    os.system("mkdir " + photos_dir)

    for frame in range(1, v['Images'] + 1):
        if not busy:
            break
        currentframe = frame


        filename = datetime.now().strftime('%H:%M:%S')+".jpg"

        os.system("fswebcam -d /dev/video0 -r 1280x720 --no-banner " + photos_dir + "/" + filename)

        # gpio.digitalWrite(motorpin, gpio.HIGH)
        # pulse = float(v['Pulse']) / 1000.0
        # sleep(pulse)
        # gpio.digitalWrite(motorpin, gpio.LOW)
        sleep(settling_time)

        # # disable the backlight, critical for night timelapses, also saves power
        # os.system("echo '0' > /sys/class/gpio/gpio252/value")
        # gpio.digitalWrite(shutterpin, gpio.HIGH)
        # sleep(shutter_length)
        # gpio.digitalWrite(shutterpin, gpio.LOW)
        # #  enable the backlight
        # os.system("echo '1' > /sys/class/gpio/gpio252/value")
        # interval = float(v['Interval']) / 1000.0
        # if (interval > shutter_length):
        #     sleep(interval - shutter_length)
    currentframe = 0
    busy = False
    threadExited = True


# def signal_handler():
#     print 'got SIGTERM'
#     pygame.quit()
#     sys.exit()


# Global stuff -------------------------------------------------------------

t = threading.Thread(target=time_lapse)
busy = False
threadExited = False
screenMode = 0  # Current screen mode; default = viewfinder
screenModePrior = -1  # Prior screen mode (for detecting changes)
iconPath = '/home/pi/LapsePiTouch/icons'  # Subdirectory containing UI bitmaps (PNG format)
numeric = 0  # number from numeric keypad
numberString = "0"
# motorRunning = 0
# motorDirection = 0
returnScreen = 0
# shutterpin = 17
# motorpinA = 18
# motorpinB = 27
# motorpin = motorpinA
# backlightpin = 252
currentframe = 0
framecount = 100
settling_time = 0.2
# shutter_length = 0.2
interval_delay = 0.2
dict_idx = "Interval"
v = {
    # "Pulse": 100,
     "Interval": 3000,
     "Images": 150}

icons = []  # This list gets populated at startup

# buttons[] is a list of lists; each top-level list element corresponds
# to one screen mode (e.g. viewfinder, image playback, storage settings),
# and each element within those lists corresponds to one UI button.
# There's a little bit of repetition (e.g. prev/next buttons are
# declared for each settings screen, rather than a single reusable
# set); trying to reuse those few elements just made for an ugly
# tangle of code elsewhere.

buttons = [

    # Screen mode 0 is main view screen of current status
    [Button((5, 180, 120, 60), bg='start', cb=start_callback, value=1),
     Button((130, 180, 60, 60), bg='cog', cb=view_callback, value=0),
     Button((195, 180, 120, 60), bg='stop', cb=start_callback, value=0)],

    # # Screen 1 for changing values and setting motor direction
    # [Button((260, 0, 60, 60), bg='cog', cb=valuesCallback, value=1),
    #  Button((260, 60, 60, 60), bg='cog', cb=valuesCallback, value=2),
    #  Button((260, 120, 60, 60), bg='cog', cb=valuesCallback, value=3),
    #  Button((0, 180, 160, 60), bg='ok', cb=valuesCallback, value=-1),
    #  Button((160, 180, 70, 60), bg='left', cb=motorCallback, value=1),
    #  Button((230, 180, 70, 60), bg='right', cb=motorCallback, value=2)],

    # Screen 2 for numeric input
    [Button((0, 0, 320, 60), bg='box'),
     Button((180, 120, 60, 60), bg='0', cb=numeric_callback, value=0),
     Button((0, 180, 60, 60), bg='1', cb=numeric_callback, value=1),
     Button((120, 180, 60, 60), bg='3', cb=numeric_callback, value=3),
     Button((60, 180, 60, 60), bg='2', cb=numeric_callback, value=2),
     Button((0, 120, 60, 60), bg='4', cb=numeric_callback, value=4),
     Button((60, 120, 60, 60), bg='5', cb=numeric_callback, value=5),
     Button((120, 120, 60, 60), bg='6', cb=numeric_callback, value=6),
     Button((0, 60, 60, 60), bg='7', cb=numeric_callback, value=7),
     Button((60, 60, 60, 60), bg='8', cb=numeric_callback, value=8),
     Button((120, 60, 60, 60), bg='9', cb=numeric_callback, value=9),
     Button((240, 120, 80, 60), bg='del', cb=numeric_callback, value=10),
     Button((180, 180, 140, 60), bg='ok', cb=numeric_callback, value=12),
     Button((180, 60, 140, 60), bg='cancel', cb=numeric_callback, value=11)]
]


# Assorted utility functions -----------------------------------------------


def save_settings():
    global v
    try:
        outfile = open('lapse.pkl', 'wb')
        # Use a dictionary (rather than pickling 'raw' values) so
        # the number & order of things can change without breaking.
        cPickle.dump(v, outfile)
        outfile.close()
    except IOError:
        pass


def load_settings():
    global v
    if os.path.isfile("lapse.pkl"):
        try:
            open1 = open('lapse.pkl', 'rb')
            infile = open1
            v = cPickle.load(infile)
            infile.close()
        except IOError:
            pass


# Initialization -----------------------------------------------------------

# Init framebuffer/touchscreen environment variables
# os.putenv('SDL_VIDEODRIVER', 'fbcon')
# os.putenv('SDL_FBDEV', '/dev/fb1')
# os.putenv('SDL_MOUSEDRV', 'TSLIB')
# os.putenv('SDL_MOUSEDEV', '/dev/input/touchscreen')

# Init pygame and screen
# print "Initting..."
# pygame.init()
# print "Setting Mouse invisible..."
# pygame.mouse.set_visible(False)
# print "Setting fullscreen..."
# modes = pygame.display.list_modes(16)
# screen = pygame.display.set_mode(modes[0], FULLSCREEN, 16)

"Ininitializes a new pygame screen using the framebuffer"
# Based on "Python GUI in Linux frame buffer"
# http://www.karoltomala.com/blog/?p=679
disp_no = os.getenv("DISPLAY")
if disp_no:
    print "I'm running under X display = {0}".format(disp_no)

# Check which frame buffer drivers are available
# Start with fbcon since directfb hangs with composite output
drivers = ['fbcon', 'directfb', 'svgalib']
found = False
for driver in drivers:
    # Make sure that SDL_VIDEODRIVER is set
    if not os.getenv('SDL_VIDEODRIVER'):
        os.putenv('SDL_VIDEODRIVER', driver)
    try:
        pygame.display.init()
        found = True
    except pygame.error:
        print 'Driver: {0} failed.'.format(driver)
        continue
    break

if not found:
    raise Exception('No suitable video driver found!')

size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
print "Framebuffer size: %d x %d" % (size[0], size[1])
screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
# Clear the screen to start
screen.fill((0, 0, 0))
# Initialise font support
pygame.font.init()
# Render the screen
pygame.display.update()

print "Loading Icons..."
# Load all icons at startup.
for icon in os.listdir(iconPath):
    if fnmatch.fnmatch(icon, '*.png'):
        icons.append(Icon(icon.split('.')[0]))
# Assign Icons to Buttons, now that they're loaded
print"Assigning Buttons"
for s in buttons:  # For each screenful of buttons...
    for b in s:  # For each button on screen...
        for i in icons:  # For each icon...
            if b.bg == i.name:  # Compare names; match?
                b.iconBg = i  # Assign Icon to Button
                b.bg = None  # Name no longer used; allow garbage collection
            if b.fg == i.name:
                b.iconFg = i
                b.fg = None

# Set up GPIO pins
# print "Init GPIO pins..."
# gpio = wiringpi2.GPIO(wiringpi2.GPIO.WPI_MODE_GPIO)
# gpio.pinMode(shutterpin, gpio.OUTPUT)
# gpio.pinMode(motorpinA, gpio.OUTPUT)
# gpio.pinMode(motorpinB, gpio.OUTPUT)
# gpio.pinMode(motorpinB, gpio.OUTPUT)
# gpio.digitalWrite(motorpinA, gpio.LOW)
# gpio.digitalWrite(motorpinB, gpio.LOW)
# # I couldnt seem to get at pin 252 for the backlight using the usual method above,
# # but this seems to work
# os.system("echo 252 > /sys/class/gpio/export")
# os.system("echo 'out' > /sys/class/gpio/gpio252/direction")
# os.system("echo '1' > /sys/class/gpio/gpio252/value")

# print"Load Settings"
load_settings()  # Must come last; fiddles with Button/Icon states

print "loading background.."
img = pygame.image.load(os.path.join(iconPath,"LapsePi.png"))

if img is None or img.get_height() < 240:  # Letterbox, clear background
    screen.fill(0)
if img:
    screen.blit(img,
                ((480 - img.get_width()) / 2,
                 (320 - img.get_height()) / 2))
pygame.display.update()
sleep(2)

# Main loop ----------------------------------------------------------------

# signal.signal(signal.SIGTERM, signal_handler)

print "mainloop.."
running = True
while running:

    # Process touchscreen input
    while running:
        for event in pygame.event.get():
            if event.type is MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                for b in buttons[screenMode]:
                    if b.selected(pos): break
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False  # Be interpreter friendly
                    pygame.quit()
                    quit()
            # elif (event.type is MOUSEBUTTONUP):
        # motorRunning = 0
        # gpio.digitalWrite(motorpinA, gpio.LOW)
        # gpio.digitalWrite(motorpinB, gpio.LOW)

        if screenMode >= 0 or screenMode != screenModePrior: break

    if img is None or img.get_height() < 240:  # Letterbox, clear background
        screen.fill(0)
    if img:
        screen.blit(img,
                    ((320 - img.get_width()) / 2,
                     (240 - img.get_height()) / 2))

    # Overlay buttons on display and update
    for i, b in enumerate(buttons[screenMode]):
        b.draw(screen)
    if screenMode == 2:
        myfont = pygame.font.SysFont("Arial", 50)
        label = myfont.render(numberString, 1, (255, 255, 255))
        screen.blit(label, (10, 2))
    if screenMode == 1:
        myfont = pygame.font.SysFont("Arial", 30)
        # label = myfont.render("Pulse:", 1, (255, 255, 255))
        # screen.blit(label, (10, 10))
        label = myfont.render("Interval:", 1, (255, 255, 255))
        screen.blit(label, (10, 70))
        label = myfont.render("Frames:", 1, (255, 255, 255))
        screen.blit(label, (10, 130))

        # label = myfont.render(str(v['Pulse']) + "ms", 1, (255, 255, 255))
        # screen.blit(label, (130, 10))
        label = myfont.render(str(v['Interval']) + "ms", 1, (255, 255, 255))
        screen.blit(label, (130, 70))
        label = myfont.render(str(v['Images']), 1, (255, 255, 255))
        screen.blit(label, (130, 130))

    if screenMode == 0:
        myfont = pygame.font.SysFont("Arial", 30)
        # label = myfont.render("Pulse:", 1, (255, 255, 255))
        # screen.blit(label, (10, 10))
        label = myfont.render("Interval:", 1, (255, 255, 255))
        screen.blit(label, (10, 50))
        label = myfont.render("Frames:", 1, (255, 255, 255))
        screen.blit(label, (10, 90))
        label = myfont.render("Remaining:", 1, (255, 255, 255))
        screen.blit(label, (10, 130))

        # label = myfont.render(str(v['Pulse']) + "ms", 1, (255, 255, 255))
        # screen.blit(label, (160, 10))
        label = myfont.render(str(v['Interval']) + "ms", 1, (255, 255, 255))
        screen.blit(label, (160, 50))
        label = myfont.render(str(currentframe) + " of " + str(v['Images']), 1, (255, 255, 255))
        screen.blit(label, (160, 90))

        # intervalLength = float((v['Pulse'] + v['Interval'] + (settling_time * 1000) + (shutter_length * 1000)))
        intervalLength = float((v['Interval'] + (settling_time * 1000)))
        remaining = float((intervalLength * (v['Images'] - currentframe)) / 1000)
        sec = timedelta(seconds=int(remaining))
        d = datetime(1, 1, 1) + sec
        remainingStr = "%dh%dm%ds" % (d.hour, d.minute, d.second)

        label = myfont.render(remainingStr, 1, (255, 255, 255))
        screen.blit(label, (160, 130))
    pygame.display.update()

    screenModePrior = screenMode
