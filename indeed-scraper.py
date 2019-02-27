import urllib.request
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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

def gen_idds(url, driver):

	driver.get(url)

	resume_links = []
	try:
		resume_links = driver.find_elements_by_css_selector('.icl-TextLink.icl-TextLink--primary.rezemp-u-h4')
	except TimeoutException:
		# could not complete in time 
		resume_links = []
	finally:
		idds = [link.get_attribute('href') for link in resume_links]
		idds = [idd[idd.rfind('/')+1:idd.rfind('?')] for idd in idds]

	return idds

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


def gen_resume(idd, driver):
	resume_url = INDEED_RESUME_BASE_URL % idd

	driver.get(resume_url)
	p_element = driver.page_source
	soup = BeautifulSoup(p_element, 'html.parser')

	resume_details = {}

	resume_body = soup.find('div', attrs={"class":"rezemp-ResumeDisplay-body"})

	summary = resume_body.contents[0]
	resume_details['summary'] = produce_summary(summary)

	resume_subsections = resume_body.find_all('div', attrs={"class":"rezemp-ResumeDisplaySection"})

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

def mine(filename, URL, override=True, search_range=None, steps=NUM_INDEED_RESUME_RESULTS, driver=FIREFOX):
	if driver == FIREFOX:
		driver = webdriver.Firefox()
	else:
		driver = webdriver.Chrome()
	driver.implicitly_wait(10)

	if override:
		# implicitly empty file
		open(filename, 'w').close()

	search = search_range[0]
	end = search_range[1]

	try:
		while search < end:
			stri = URL + '&' + urlencode({'start': search})
			idds = gen_idds(stri, driver)

			if(len(idds) == 0):
				# immediately stop
				sys.stderr.write('Unable to find any resumes at index %d\n' % search)
				break
			
			# move to the next results irrespective
			search += steps
			with open(filename, 'a') as outfile:
				# really only needed because to make
				# small number of resumes for testing
				for i in range(min(steps, len(idds))):
					outfile.write(gen_resume(idds[i], driver).toJSON() + "\n")
	finally:
		print('Driver shutting down')
		driver.close()
	
	return filename

def mine_multi(args, search_URL):
	start = args.si
	end = args.ei
	tr = args.threads
	steps = ceil((end - start) / tr)
	starting_points = list(range(start, end, steps))
	fs = []

	with concurrent.futures.ThreadPoolExecutor(max_workers=tr) as executor:
		for idx, search_start in enumerate(starting_points):
			# Instantiates the thread
			filename = OUTPUT_BASE_NAME + args.name + str(idx) + '.json'
			search_range = (search_start, end if idx + 1 == len(starting_points) else starting_points[idx + 1])
			mine_args = (filename, search_URL)
			mine_kwargs = {
				"override" : args.override,
				"search_range" : search_range,
				"steps": min(end - starting_points[idx], steps, NUM_INDEED_RESUME_RESULTS),
				"driver": args.driver
			}
			fs.append(executor.submit(mine, *mine_args, **mine_kwargs))
			
		filenames = []
		try:
			for fut in concurrent.futures.as_completed(fs):
				filenames.append(fut.result())
		except (KeyboardInterrupt, Exception) as e:
			sys.stderr.write('Caught exception %s of type %s, cleaning up results\n' % (str(e), type(e)))
			clean_up_all_results(args.name)
		else:
			consolidate_files(args.name, filenames, args.override)

def consolidate_files(name, names, override=True):
	mode = 'w' if override else 'a'
	file = open("resume_output_" + name + ".json", mode)
	for nam in names:
		with open(nam, 'r') as read:
			file.write(read.read())
		os.remove(nam)
			
	file.close()

def clean_up_all_results(name):
	output_glob = OUTPUT_BASE_NAME + name + '*' + '.json'
	print(output_glob)
	files = glob.glob(output_glob)
	for file in files:
		os.remove(file)

def main(args):
	t = time.clock()
	# restrict search only to job titles skills and field of study
	query = {
		'q': args.q,
		'l': args.l,
		'searchFields': 'jt,skills,fos'
	}
	query_string = urlencode(query)
	search_URL= INDEED_RESUME_SEARCH_BASE_URL % query_string

	mine_multi(args, search_URL)
	print(time.clock() - t),

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
	parser.add_argument('--threads', default=8, type=int, metavar='threads', help='# of threads to run')
	parser.add_argument('--override', default=False, action='store_true', help='override existing result if any')
	parser.add_argument('--driver', default=FIREFOX, choices=[FIREFOX, CHROME])

	args = parser.parse_args()

	# in case of carrige returns
	args.q = args.q.strip()
	args.l = args.l.strip()
	args.name = args.name.strip()
	args.name = args.name.replace(' ', '-')
	main(args)