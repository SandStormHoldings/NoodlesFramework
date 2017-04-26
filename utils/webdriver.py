import selenium
import os
from noodles.utils.helpers import get_config
from pyvirtualdisplay import Display
from selenium.webdriver.remote import webdriver


def wd_instance(driver_name, port=9515):
    remurl = 'http://%s:%s/' % (get_config('CHROMEDRIVER_HOST'), port)
    if driver_name == 'firefox':
        driver = webdriver.Firefox()
    elif driver_name in ('chrome', 'mobile_chrome', 'ie6'):
        capabilities = {}
        if driver_name == 'mobile_chrome':
            user_agent = "Mozilla/5.0 "\
                         "(iPhone; CPU iPhone OS 5_0 like Mac OS X) "\
                         "AppleWebKit/534.46 (KHTML, like Gecko) "\
                         "Version/5.1 Mobile/9A334 Safari/7534.48.3"
            capabilities = selenium.webdriver.DesiredCapabilities.CHROME
            capabilities["chrome.switches"] = ["--user-agent=" + user_agent]
        elif driver_name == 'ie6':
            user_agent = "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 6.0)"
            capabilities["chrome.switches"] = ["--user-agent=" + user_agent]

        if get_config('CHROMEDRIVER_VIRTUAL_DISPLAY'):
            chromedriver = get_config('CHROMEDRIVER_BINARY')
            os.environ['webdriver.chrome.driver'] = chromedriver
            display = Display(visible=0, size=(800, 600))
            display.start()
            try:
                driver = selenium.webdriver.Chrome(chromedriver)
            except:
                raise Exception(
                    'failed to instantiate webdriver '
                    'with binary path %s' % chromedriver)
        else:
            try:
                driver = selenium.webdriver.Remote(
                    remurl, desired_capabilities=capabilities)
            except Exception, e:
                raise Exception('could not connect to selenium at %s; '
                                'CHECK THAT YOU HAVE CHROMEDRIVER RUNNING - '
                                'http://code.google.com/p/chromedriver/'
                                'downloads/list'
                                'Exception: %s'% ( remurl,str(e)))
    else:
        raise Exception('Driver not defined!')
    return driver
