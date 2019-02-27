import urllib.request
import requests
from selenium.webdriver import firefox, chrome
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time
import json
import threading
from random import randint
from time import sleep
from math import ceil
import os
import argparse
from urllib.parse import quote_plus, urlencode
import traceback
import sys
import glob
import concurrent.futures
import platform

NUM_INDEED_RESUME_RESULTS = 50
INDEED_RESUME_BASE_URL = 'https://resumes.indeed.com/resume/%s'
INDEED_RESUME_SEARCH_BASE_URL = 'https://resumes.indeed.com/search/?%s'

# RESUME SUBSECTIONS TITLE (in normal setting)
WORK_EXPERIENCE = 'Work Experience'
EDUCATION = 'Education'
SKILLS = 'Skills'
CERTIFICATIONS = 'Certifications'
ADDITIONAL_INFORMATION = 'Additional Information'

# INDICES
SKILL_NAME_INDEX = 0
SKILL_EXP_INDEX = 1
INFO_CONTENT_DETAILS_INDEX = 0

# RESULT FILE BASE NAME
OUTPUT_BASE_NAME = 'resume_output_'

# DRIVERS
FIREFOX = 'firefox'
CHROME = 'chrome'

# LOGIC
MAX_RETRIES = 3
SLEEP_TIME = 3 
MAX_WAIT = 3

CTRL_COMMAND = Keys.COMMAND if platform.platform() == 'Darwin' else Keys.CONTROL

class Resume:
	def __init__ (self, idd, **kwargs):
		self.id = idd
		self.summary = kwargs.get('summary')
		self.jobs = kwargs.get('jobs')
		self.schools = kwargs.get('schools')
		self.skills = kwargs.get('skills')
		self.additional = kwargs.get('additional')

	def toJSON(self):
		return json.dumps(self, default=lambda o: o.__dict__)

class Summary:
	def __init__(self, details):
		self.details = details

class Job:
	def __init__(self, title, company, work_dates, details):
		self.title = title
		self.company = company

		dates = work_dates.split(' to ')
		self.start_date = dates[0]
		self.end_date = '' if len(dates) == 1 else dates[1]

		self.details = details

class School:
	def __init__(self, degree, school_name, grad_date):
		self.degree = degree
		self.school_name = school_name
		self.start_date = ''
		self.end_date = ''

		if grad_date is not None:
			dates = grad_date.split(' to ')
			self.start_date = dates[0]
			self.end_date = '' if len(dates) == 1 else dates[1]

class Skill:
	def __init__(self, skill, experience):
		self.skill = skill
		self.experience = experience

class Info:
	def __init__(self, details):
		self.details = details

def gen_resume_link_elements(driver):
	"""Generate IDDs of resume
	
	Assumes driver already in page with resume IDDs

	Returns list of WebElement
	"""

	resume_links = []
	try:
		resume_links = driver.find_elements_by_css_selector(
			'div.rezemp-ResumeSearchCard .icl-TextLink.icl-TextLink--primary.rezemp-u-h4'
		)
	except TimeoutException:
		# could not complete in time 
		resume_links = []

	return resume_links

def produce_work_experience(worksection):
	work_experience = worksection.find_all('div', class_='rezemp-WorkExperience')
	jobs = []
	for experience in work_experience:
		job_title = experience.find('div', class_='rezemp-u-h4').get_text()
		company_and_dates = experience.find('div', class_='rezemp-WorkExperience-subtitle')

		company_name = company_and_dates.find('span', class_='icl-u-textBold').get_text()
		work_dates = company_and_dates.find('div', class_='icl-u-textColor--tertiary').get_text()
		job_details = []
		if len(experience.contents) == 3:
			# there are job details
			details = experience.contents[-1]
			job_details = [detail for detail in details.stripped_strings]

		jobs.append(Job(job_title, company_name, work_dates, job_details))
	return jobs

def produce_education(edusection):
	content = edusection.find('div', class_='rezemp-ResumeDisplaySection-content')
	schools = []
	for school in content.children:
		degree = school.find(class_ = "rezemp-ResumeDisplay-itemTitle")
		if degree is not None:
			degree = degree.get_text(' ', strip=True)
		university_details = school.find(class_="rezemp-ResumeDisplay-university")
		school_name = university_details.find('span', class_='icl-u-textBold')
		if school_name is not None:
			school_name = school_name.get_text()
		date = school.find(class_="rezemp-ResumeDisplay-date")
		if date is not None:
			date = date.get_text()
		schools.append(School(degree, school_name, date))
	return schools

def produce_skills(skillsection):
	content = skillsection.find('div', class_='rezemp-ResumeDisplaySection-content')
	skills = []
	for skill_details in content.children:
		if skill_details.string is None:
			# there is no string attribute,
			# so it must be nested and so must be an actual skill
			# find skill detail spans
			skill_spans = skill_details.span.find_all('span')
			skill = skill_spans[SKILL_NAME_INDEX].get_text()
			experience = ''
			if len(skill_spans) == 2:
				experience = skill_spans[SKILL_EXP_INDEX].get_text()
			skills.append(Skill(skill, experience))
	return skills

# in case if needed later on in the future
def produce_certifications_license():
	pass

def produce_additional(infosection):
	content = infosection.find('div', class_='rezemp-ResumeDisplaySection-content')
	# only one div in content
	info_details = content.contents[INFO_CONTENT_DETAILS_INDEX]
	return [detail for detail in info_details.stripped_strings]


def produce_summary(summarysection):
	summary_details = []
	if len(summarysection) == 4:
  		summary_details = summarysection.contents[-1]
  		summary_details = [detail for detail in summary_details.stripped_strings]

	return summary_details


def gen_resume(resume_link, driver):
	idd = resume_link[resume_link.rfind('/') + 1:resume_link.rfind('?')]
	print('Processing resume ID', idd)
	try:
		WebDriverWait(driver, MAX_WAIT).until(
			EC.visibility_of_any_elements_located((By.CLASS_NAME, 'rezemp-ResumeDisplay-body'))
		)
	except TimeoutException:
		sys.stderr.write('Unable to get resume for ID %s, abandoning fetch' % idd)
		return None

	p_element = driver.page_source
	soup = BeautifulSoup(p_element, 'html.parser')
	resume_body = soup.find('div', attrs={"class":"rezemp-ResumeDisplay-body"})

	summary = resume_body.contents[0]
	resume_subsections = resume_body.find_all('div', attrs={"class":"rezemp-ResumeDisplaySection"})

	resume_details = {}
	resume_details['summary'] = produce_summary(summary)
	for subsection in resume_subsections:
		children = subsection.contents
		subsection_title = children[0].get_text()
		if subsection_title == WORK_EXPERIENCE:
			resume_details['jobs'] = produce_work_experience(subsection)
		elif subsection_title == EDUCATION:
			resume_details['schools'] = produce_education(subsection)
		elif subsection_title == SKILLS:
			resume_details['skills'] = produce_skills(subsection)
		elif subsection_title == CERTIFICATIONS:
			produce_certifications_license()
		elif subsection_title == ADDITIONAL_INFORMATION:
			resume_details['additional'] = produce_additional(subsection)
		else:
			print('ID', idd, '- Subsection title is', subsection_title)

	return Resume(idd, **resume_details)

def go_to_next_search_page(driver):
	try:
		next_button = driver.find_element_by_class_name('rezemp-pagination-nextbutton')
		# not sure why but next_button.click() does not always work across firefox and chrome
		driver.execute_script("arguments[0].click();", next_button)
	except NoSuchElementException:
		print('No more pages to go to')
		return False

	return True

def mine(args, json_file, search_URL):
	if args.driver == FIREFOX:
		fp = firefox.firefox_profile.FirefoxProfile()
		fp.set_preference("browser.tabs.remote.autostart", False)
		fp.set_preference("browser.tabs.remote.autostart.1", False)
		fp.set_preference("browser.tabs.remote.autostart.2", False)
		driver = firefox.webdriver.WebDriver(firefox_profile=fp)
	else:
		driver = chrome.webdriver.WebDriver()
	driver.implicitly_wait(MAX_WAIT)

	search = args.si
	end = args.ei

	attempts = 0
	# actions = ActionChains(driver)
	try:
		search_point = search_URL + '&' + urlencode({'start': search})
		continue_search = True
		driver.get(search_point)
		main_window = driver.current_window_handle
		while search < end and continue_search:
			link_elements = gen_resume_link_elements(driver)

			if len(link_elements) == 0 and attempts < MAX_RETRIES:
				# attempt retry
				sys.stderr.write('Unable to find any resumes at index %d. Retrying in %d seconds...\n' % (search, SLEEP_TIME))
				sys.stderr.flush()
				attempts += 1
				time.sleep(SLEEP_TIME)
			elif len(link_elements) == 0 and attempts == MAX_RETRIES:
				sys.stderr.write('Unable to find any resumes at index %d. Reached max attempts, abandoning search...\n' % search)
				continue_search = False
			else:
				for link in link_elements[:min(len(link_elements), end - search)]:
					resume_link = link.get_attribute('href')
					# seems to not work for firefox (at least on MAC)
					# actions.reset_actions()
					# actions.key_down(CTRL_COMMAND, link).click(link).perform()
					link.send_keys(CTRL_COMMAND + Keys.SHIFT + Keys.RETURN) # without shift firefox seems to not work on Mac
					driver.switch_to.window(driver.window_handles[1])
					resume = gen_resume(resume_link, driver)
					driver.close()
					driver.switch_to.window(main_window)
					if resume is not None:
						json_file.write(resume.toJSON() + "\n")
					search += 1

				continue_search = go_to_next_search_page(driver)
				print('Finished getting %d resumes, going to sleep a bit' % search)
				time.sleep(SLEEP_TIME)			
	finally:
		print('Driver shutting down')
		driver.close()

def main(args):
	t = time.perf_counter()
	# restrict search only to job titles skills and field of study
	query = {
		'q': args.q,
		'l': args.l,
		'searchFields': 'jt',
		'lmd': 'all'
	}
	query_string = urlencode(query)
	search_URL= INDEED_RESUME_SEARCH_BASE_URL % query_string

	try:
		filename = OUTPUT_BASE_NAME + args.name + '.json'
		if args.override:
			# implicitly empty file
			open(filename, 'w').close()
			
		with open(filename, 'a') as json_file:
			mine(args, json_file, search_URL)
	except KeyboardInterrupt:
		print('Interrupted by keyboard, exiting soon...')

	print("Finished in %f seconds" % (time.perf_counter() - t)),

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description='Scrape Indeed Resumes',
		formatter_class=argparse.ArgumentDefaultsHelpFormatter
	)
	required_arguments = parser.add_argument_group(title='required arguments')
	required_arguments.add_argument('-q', metavar='query', required=True, help='search query to run on indeed e.g software engineer')
	required_arguments.add_argument('--name', metavar='name', required=True, help='name of search (used to save files, spaces turned to "-")')

	parser.add_argument('-l', default='Canada', metavar='location', help='location scope for search')
	parser.add_argument('-si', default=0, type=int, metavar='start', help='starting index (multiples of 50)')
	parser.add_argument('-ei', default=5000, type=int, metavar='end', help='ending index (multiples of 50)')
	parser.add_argument('--override', default=False, action='store_true', help='override existing result if any')
	parser.add_argument('--driver', default=FIREFOX, choices=[FIREFOX, CHROME])

	args = parser.parse_args()

	# in case of carrige returns
	args.q = args.q.strip()
	args.l = args.l.strip()
	args.name = args.name.strip()
	args.name = args.name.replace(' ', '-')
	main(args)