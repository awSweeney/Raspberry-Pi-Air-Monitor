#!/user/bin/env python3

"""
Description:
Interface for running an air environment monitor on Raspberry Pi.
"""

# Python Standard Imports
import datetime
import time
import configparser

# Raspberry Pi Imports
import RPi.GPIO as GPIO
import dht11
import lcddriver
from Adafruit_IO import RequestError, Client, Feed


class AirMonitor:

    def __init__(self):
        self.temperature_celsius = None
        self.temperature_fahrenheit = None
        self.humidity = None

        GPIO.setwarnings(True)
        GPIO.setmode(GPIO.BCM)

        self.config = configparser.ConfigParser()
        self.config.read('AirMonitor.cfg')
        self.SetupSesnors()

        if self.config['DISPLAY']['ENABLED'].upper() == 'Y':
            self.display = lcddriver.lcd()

        if self.config['ADAFRUIT_IO']['ENABLED'].upper() == 'Y':
            self.adafruit_last_upload = None
            self.aio = Client(
                self.config['ADAFRUIT_IO']['USER'], 
                self.config['ADAFRUIT_IO']['KEY'])

    def Run(self):
        """Main run sequence
        """
        while True:
            self.GetEnvironmentMetrics()
            self.LogResults()

            if self.config['DISPLAY']['ENABLED'].upper() == 'Y':
                self.UpdateLCDDisplay()

            self.AdafruitUpload()

            time.sleep(int(self.config['DEFAULT']['UPDATE_INTERVAL']))
    
    def _FormatResult(self, unformatted_value):
        """Formats a value to a single precision floating point

        :param unformatted_value: Value to format
        :type unformatted_value: float
        :return: Formatted value
        :rtype: float
        """
        value = '{0:.3g}'.format(unformatted_value)
        if '.' in value:
            value = value.rstrip('0')
        return value

    def _ctof(self, celsius_temperature):
        """Helper to convert celsius to fahrenheit

        :param celsius_temperature: celsius value to convert
        :type celsius_temperature: float
        :return: Fahrenheit temperature
        :rtype: float
        """
        return (celsius_temperature * (9/5)) + 32

    def AdafruitUpload(self):
        """Upload observed values to Adafruit IO
        """
        if self.config['ADAFRUIT_IO']['ENABLED'].upper() == 'Y':

            if not self.adafruit_last_upload or \
            datetime.datetime.now() >= self.adafruit_last_upload + \
                datetime.timedelta(
                    minutes=int(self.config['ADAFRUIT_IO']['UPLOAD_INTERVAL'])):
                
                values = self.GetValueDict()

                for key in values:
                    if values[key]:
                        try:
                            feed = self.aio.feeds(feed=key)
                        except RequestError:
                            feed = Feed(name=key)
                            feed = self.aio.create_feed(feed)

                        self.aio.send_data(feed.key, values[key])
                self.adafruit_last_upload = datetime.datetime.now()
    
    def Cleanup(self):
        """Run cleanup and shutdown tasks
        """
        self.Log("Shutting Down")
        GPIO.cleanup()

    def DHT11Read(self):
        """Read data from a DHT11 sensor
        """
        result = self.dht_sensor.read()

        if result.is_valid():
            corrected_temperature = result.temperature + \
                float(self.config['DHT11']['TEMPERATURE_CALIBRATION'])
            corrected_humidity = result.humidity + \
                float(self.config['DHT11']['HUMIDITY_CALIBRATION'])
            self.temperature_celsius = self._FormatResult(
                corrected_temperature)
            self.temperature_fahrenheit = self._FormatResult(
                self._ctof(corrected_temperature))
            self.humidity = self._FormatResult(corrected_humidity)
        else:
            self.Log("DHT11 Error: %d" % result.error_code)

    def GetEnvironmentMetrics(self):
        """Collect data from the available sensors
        """
        if self.dht_sensor:
            self.DHT11Read()

    def GetValueDict(self):
        """Get data values in dict format

        :return: Observed data values
        :rtype: dict
        """
        return {'fahrenheit': self.temperature_fahrenheit,
                'celsius': self.temperature_celsius,
                'humidity': self.humidity
                }

    def Log(self, message):
        """Logging wrapper

        :param message: Message to log
        :type message: string
        """
        if self.config['LOGGING']['CONSOLE_ENABLED'].upper() == 'Y':
            print(message)

    def LogResults(self):
        """Log data results
        """
        self.Log(f"{datetime.datetime.now()}")
        self.Log(f"celsius: {self.temperature_celsius}C")
        self.Log(f"Fahrenheit: {self.temperature_fahrenheit}F")
        self.Log(f"Humidity: {self.humidity}%")

    def SetupSesnors(self):
        """Initializes sensors

        :raises Exception: If invalid sensor configuration provided
        """
        if self.config['ENV_SENSOR']['TYPE'] == 'DHT11':
            self.dht_sensor = dht11.DHT11(pin=int(self.config['DHT11']['PIN']))
        else:
            raise Exception('Invalid sensor defined')

    def UpdateLCDDisplay(self):
        """Update the LCD display
        """
        self.display.lcd_clear()
        self.display.lcd_display_string(f'{datetime.datetime.now()}', 1)
        self.display.lcd_display_string(
            f'T|{self.temperature_fahrenheit}F H|{self.humidity}%', 2)

if __name__ == '__main__':

    monitor = AirMonitor()

    try:
        monitor.Run()
    except Exception:
        raise
    finally:
        monitor.Cleanup()
