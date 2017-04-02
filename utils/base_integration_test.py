# -*- coding: utf-8 -*-
"""
Base Selenium test methods
"""
import sys
import uuid
import json
import time
import unittest
import urllib2
import warnings

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from noodles.utils.logger import log
from noodles.utils.helpers import get_config

from unittest.case import (
    _UnexpectedSuccess,
    _ExpectedFailure,
    SkipTest,
)


def get_browser_errors(driver):
    return [m.get('message') for m in driver.get_log('browser')
            if m.get('level') == 'SEVERE'
            ]


class BaseTest(unittest.TestCase):
    def __init__(self, testname, kwargs=None):
        self.e = None
        self.driver = None
        self.suite_id = None
        self.test_id = uuid.uuid4().hex
        self.method = None
        self.locator = None
        self.url_response = None
        self.testname = "self." + testname
        self.__dict__.update(kwargs)
        self.clean()
        setattr(self, self.method, eval(self.testname))
        super(BaseTest, self).__init__(self.method)

    def setUp(self):
        self.verificationErrors = []

    def tearDown(self):
        self.assertEqual([], self.verificationErrors)

    def clean(self):
        clean_list = ['"', "'", ":", "/", "\\", ".", ", ", "[", "]"]
        clean_method = []
        for letter in self.method:
            if clean_list.count(letter) < 1:
                clean_method.append(letter)
        self.method = ''.join(str(n) for n in clean_method)

    def open_location(self):
        """
        Equal target location with real location
        """
        try:
            self.assertEqual(self.test_location, self.selenium.get_location())
        except AssertionError, self.e:
            self.verificationErrors.append(str(self.e))

    def get_text(self):
        try:
            self.assertEqual(self.locator.split("=")[1],
                             self.selenium.get_text(self.locator))
        except AssertionError, self.e:
            self.verificationErrors.append(str(self.e))

    def assert_url_response(self):
        try:
            urllib2.urlopen(self.url_response)
        except AssertionError, self.e:
            self.verificationErrors.append(str(self.e))

    def verify_equal_find_element_by_css_selector_text(self):
        """
        If locator and text in selector not equal then this test mark as error
        """
        try:
            self.assertEqual(self.locator[0],
                             self.driver.find_element_by_css_selector(
                                 self.locator[1]).text)
        except AssertionError as e:
            self.driver.get_screenshot_as_file(
                "tests/reports/%s_FALSE.png" % self.method)
            self.verificationErrors.append(str(e))

    def assert_equal_find_element_by_css_selector_attr_text(self):
        """
        If locator and attribute text in selector not equal
        then set this test as failure
        """
        self.assertEqual(self.locator[0],
                         self.driver.find_element_by_css_selector(
                             self.locator[1]).get_attribute(self.locator[2]))

    def assert_true_element_by_name(self):
        """
        If element not found by name then make then set this test as failure
        """
        self.assertTrue(self.is_element_present(By.NAME, self.locator))

    def is_element_present(self, how, what):
        try:
            self.driver.find_element(by=how, value=what)
        except NoSuchElementException, self.e:
            self.driver.get_screenshot_as_file(
                "../../reports/%s_%s_FALSE.png" % (what, self.method))
            return False
        return True

    def check_virtual(self, max_time):
        timeout = 0
        result = False
        while timeout <= max_time:
            channel_state = 0
            time.sleep(0.5)
            timeout += 1
            state = self.driver.execute_script(
                "return (window.APISOCKET ? JSON.stringify(window.APISOCKET.virtualsockets) : null)")
            if state:
                virtual = json.loads(state)
                channels = len(virtual.keys())
                for name in virtual.keys():
                    channel = virtual.get(name)
                    if channel.get('open', False):
                        channel_state += 1
                        continue
                if channel_state != channels:
                    continue
                result = True
                break
        if not result:
            self.verificationErrors.append("%s\n%s" % (type(state), state))
        return

    def is_text_present(self):
        try:
            self.failUnless(self.selenium.is_text_present(self.locator))
        except AssertionError, self.e:
            self.verificationErrors.append(str(self.e))

    def is_tracked(self):
        result = get_config('TRACK_TESTS_EXECUTION', False)
        return result

    def pre_set_up(self):
        if not self.is_tracked():
            return

        data = {
            'job': get_config('JOB', ''),
            'suite_id': self.suite_id,
            'test_id': self.test_id,
            'testname': self.testname,
            'method': self._testMethodName,
            'class': str(self.__class__),
            'timestamp': time.ctime(),
        }
        track_file_name = get_config('TRACK_FILE_NAME', 'api_debug.json')
        with open(track_file_name, 'w') as f:
            f.write(json.dumps(data))

    def post_tear_down(self):
        pass

    def safe_exec(self, fn):
        """
        Must never fall
        """
        try:
            fn()
        except Exception as e:
            log.error(e)

    # (Yura A) it was taken from /usr/lib/python2.7/unittest/case.py
    def run(self, result=None):
        orig_result = result
        if result is None:
            result = self.defaultTestResult()
            startTestRun = getattr(result, 'startTestRun', None)
            if startTestRun is not None:
                startTestRun()

        self._resultForDoCleanups = result
        result.startTest(self)

        testMethod = getattr(self, self._testMethodName)
        if (getattr(self.__class__, "__unittest_skip__", False) or
            getattr(testMethod, "__unittest_skip__", False)):
            # If the class or method was skipped.
            try:
                skip_why = (getattr(self.__class__, '__unittest_skip_why__', '')
                            or getattr(testMethod, '__unittest_skip_why__', ''))
                self._addSkip(result, skip_why)
            finally:
                result.stopTest(self)
            return
        try:
            success = False
            try:
                self.safe_exec(self.pre_set_up)
                self.setUp()
            except SkipTest as e:
                self._addSkip(result, str(e))
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, sys.exc_info())
            else:
                try:
                    testMethod()
                    if hasattr(self, 'post_test_action'):
                        self.post_test_action()
                except KeyboardInterrupt:
                    raise
                except self.failureException:
                    result.addFailure(self, sys.exc_info())
                except _ExpectedFailure as e:
                    addExpectedFailure = getattr(result, 'addExpectedFailure', None)
                    if addExpectedFailure is not None:
                        addExpectedFailure(self, e.exc_info)
                    else:
                        warnings.warn("TestResult has no addExpectedFailure method, reporting as passes",
                                      RuntimeWarning)
                        result.addSuccess(self)
                except _UnexpectedSuccess:
                    addUnexpectedSuccess = getattr(result, 'addUnexpectedSuccess', None)
                    if addUnexpectedSuccess is not None:
                        addUnexpectedSuccess(self)
                    else:
                        warnings.warn("TestResult has no addUnexpectedSuccess method, reporting as failures",
                                      RuntimeWarning)
                        result.addFailure(self, sys.exc_info())
                except SkipTest as e:
                    self._addSkip(result, str(e))
                except:
                    result.addError(self, sys.exc_info())
                else:
                    success = True

                try:
                    self.tearDown()
                    self.safe_exec(self.post_tear_down)
                except KeyboardInterrupt:
                    raise
                except:
                    result.addError(self, sys.exc_info())
                    success = False

            cleanUpSuccess = self.doCleanups()
            success = success and cleanUpSuccess
            if success:
                result.addSuccess(self)
        finally:
            result.stopTest(self)
            if orig_result is None:
                stopTestRun = getattr(result, 'stopTestRun', None)
                if stopTestRun is not None:
                    stopTestRun()

    def get_js_errors(self):
        errors = get_browser_errors(self.driver)
        if errors != []:

            if not '(Not Found)' in str(errors):
                self.verificationErrors.append(
                    'on page %s:\n%s' % (self.driver.current_url, '\n'.join(errors)))

