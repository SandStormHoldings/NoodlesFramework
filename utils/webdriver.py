import selenium
import os
from helpers import get_config
from pyvirtualdisplay import Display
from selenium.webdriver.remote import webdriver

user_agents = {
    'chrome': "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.64 Safari/537.36",
    'mobile_chrome': "Mozilla/5.0 "
                     "(iPhone; CPU iPhone OS 7_0 like Mac OS X) "
                     "AppleWebKit/537.51.1 (KHTML, like Gecko) "
                     "Version/7.0 Mobile/11A465 Safari/9537.53",
    'ie6': "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 6.0)",
    'ie7': "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)",
    'ie8': "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0)",
    'ie9': "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
    'ie10': "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Trident/6.0)",
    'ie11': "Mozilla/5.0 (Windows NT 6.3; Trident/7.0; rv:11.0) like Gecko",
    'ff': "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:25.0) Gecko/20100101 Firefox/25.0"
}
DEFAULT_DISPLAY_SIZE=(1440,1080)


def get_driver_names():
    return user_agents.keys()


def wd_instance(driver_name, time_to_wait=30):
    """:param time_to_wait: Sets a sticky timeout to implicitly wait for an
    element to be found
    """

    display = None
    remurl = 'http://%s:%s' \
             % (get_config('CHROMEDRIVER_HOST'),
                get_config('CHROMEDRIVER_PORT'))
    if driver_name == 'firefox':
        driver = webdriver.Firefox()
    elif driver_name in user_agents.keys():
        capabilities = {}
        if driver_name == 'mobile_chrome':
            capabilities = selenium.webdriver.DesiredCapabilities.CHROME
            capabilities["chromeOptions"] = {
                'args': ['user-agent=%s' % user_agents[driver_name]],
                'extensions': []
            }
        elif driver_name != 'chrome':
            capabilities["chromeOptions"] = {
                'args': ["user-agent=%s" % user_agents[driver_name]],
                'extensions': []
            }
        if 'chromeOptions' not in capabilities:
            capabilities['chromeOptions']={'args':[]}
        capabilities['chromeOptions']['args'].append('--test-type')

        if get_config('CHROMEDRIVER_VIRTUAL_DISPLAY'):
            chromedriver = get_config('CHROMEDRIVER_BINARY')
            os.environ['webdriver.chrome.driver'] = chromedriver
            display = Display(visible=0, size=DEFAULT_DISPLAY_SIZE)
            display.start()


            options = selenium.webdriver.ChromeOptions()
            if driver_name in user_agents:
                options.add_argument('--user-agent="%s"'%user_agents[driver_name])

            try:
                driver = selenium.webdriver.Chrome(chromedriver,chrome_options=options,desired_capabilities=capabilities)
                driver.set_window_size(*DEFAULT_DISPLAY_SIZE)
                driver.set_window_position(0, 0)
            except Exception as expt:
                print(expt)
                print('-' * 80)
                raise Exception(
                    'failed to instantiate webdriver '
                    'with binary path %s' % chromedriver)
        else:
            try:
                if get_config('CHROMEDRIVER_HOST') not in ['localhost', '127.0.0.1']:
                    remurl += '/wd/hub'
                    capabilities = selenium.webdriver.DesiredCapabilities.CHROME
                driver = selenium.webdriver.Remote(
                    remurl, desired_capabilities=capabilities)
                driver.set_window_size(*DEFAULT_DISPLAY_SIZE)
                driver.set_window_position(0, 0)
            except Exception as expt:
                print('-' * 80)
                raise Exception('could not connect to selenium at %s; '
                                'CHECK THAT YOU HAVE CHROMEDRIVER RUNNING - '
                                'http://code.google.com/p/chromedriver/'
                                'downloads/list'
                                'Exception: %s' % (remurl, str(expt)))
    else:
        raise Exception('Driver not defined!')
    if not display is None:
        driver.display_stop = lambda: display.stop()
    driver.implicitly_wait(time_to_wait)
    return driver
