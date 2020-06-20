import math

from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
import time
from datetime import datetime
import os

from selenium.webdriver import Chrome
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

driver = Chrome(ChromeDriverManager().install())
data = {'Meeting': [], 'Race': [], 'Dist': [], 'Trk Cond': [], 'Horse': [], 'Tab Number': [], 'Barrier': [],
        'Open': [], 'Open Rank': []}
final_df = pd.DataFrame()


def australian_meetings(url_page):
    r = requests.get(url_page)
    s = BeautifulSoup(r.text, "html.parser")
    table = s.find("div", {"class": "racingGridContainer_f1mgyl9u"})
    table_rows = table.findAll("tr", {"class": "firstRow_f185foic"})

    def meeting_in_australia(element):
        return element.find("span", {"class": "meetingRegion_fp0l9rc"}).text == 'Australia'

    table_rows_aus = list(filter(meeting_in_australia, table_rows))

    for x in table_rows_aus:
        table_row(x)
    # table_row(table_rows_aus[0])  # Test


# Receives a meeting row and calls races_in_meeting with meeting_url
def table_row(element):
    href_to_meeting = element.find("a", href=True)['href']
    meeting_url = 'https://www.sportsbet.com.au' + href_to_meeting
    meeting(meeting_url)


# Gets all races in a meeting and calls race_in_meeting
def meeting(meeting_url):
    print(meeting_url)
    r = requests.get(meeting_url)
    s = BeautifulSoup(r.text, "html.parser")
    races_table = s.find("div", {"class": "list_fnkfoee"})
    races_rows = races_table.findAll("div", {"class": "rowWithBorder_f1cm2uvn"})

    for x in races_rows:
        meeting_row(x)
    # meeting_row(races_rows[0])  # Test

    # write_sheet(meeting_url.split('/')[-2])  # Separate in sheets


# Receives a race row and calls race with race_url
def meeting_row(race_element):
    href_to_race = race_element.find("a", href=True)['href']
    race_url = 'https://www.sportsbet.com.au' + href_to_race
    print(race_url)
    race(race_url)


# In charge of creating the pandas
def race(race_url):
    r = requests.get(race_url)
    s = BeautifulSoup(r.text, "html.parser")

    meeting_name = s.select("h1.titilliumWebBlack_fowl7b1")[0].text.strip()
    meeting_name = re.findall('[A-Z][^A-Z]*', meeting_name)[0]
    race_full_name = s.find("div", {"class": "raceTitleStreamingContainer_f1nvegwb"}).text
    race_dist = race_full_name.split()[0]
    race_number = race_full_name.split()[1]
    trk_cond = s.find("div", {"class": "container_f1z10v5r"}).text
    if trk_cond != 'Synthetic':
        trk_cond = trk_cond[0] + trk_cond[-2]

    horses_rows = s.findAll("div", {"class": "outcomeDetails_fgw55bl"})

    driver.get(race_url)
    delay = 10  # seconds
    try:
        WebDriverWait(driver, delay).until(
            ec.presence_of_element_located((By.CLASS_NAME, 'background_fja218n')))
        print("Page is ready!")
    except TimeoutException:
        print("Loading page took too much time!")

    for i, x in enumerate(horses_rows):
        data['Meeting'].append(meeting_name)
        data['Race'].append(race_number)
        data['Dist'].append(race_dist[:-1])
        data['Trk Cond'].append(trk_cond)
        horse_info(x, i)
    # horse_info(horses_rows[0])    # Test

    calculate_open_rank()


def horse_info(horse_element, index):
    open_container = driver.find_elements_by_xpath("//div[contains(@class, 'priceFlucsContainer_f1qh6j2w')]")

    horse_full_name = horse_element.find("span", {"class": "medium_f1wf24vo"})

    if not horse_full_name:
        data['Meeting'].pop()
        data['Race'].pop()
        data['Dist'].pop()
        data['Trk Cond'].pop()
        return

    horse = horse_full_name.text[3:]
    tab_number = horse_full_name.text.split('.')[0]
    barrier = horse_element.find("span", {"class": "light_f2noysy"}).text[2:][:-1]

    open_c = open_container[index].find_element_by_tag_name('span').text

    if open_c == '':
        open_c = 999.99

    data['Horse'].append(horse)
    data['Tab Number'].append(tab_number)
    data['Barrier'].append(barrier)
    data['Open'].append(open_c)
    data['Open Rank'].append(0)


def calculate_open_rank():
    global data, final_df
    counter = 1
    df = pd.DataFrame.from_dict(data)
    convert_dict = {'Tab Number': int, 'Open': float, 'Open Rank': float}
    df = df.astype(convert_dict)

    df = df.sort_values('Open')
    df = df.reset_index(drop=True)

    for index, row in df.iterrows():
        df.at[index, 'Open Rank'] = counter
        if counter > 1:
            if df.at[index - 1, 'Open'] == df.at[index, 'Open']:
                if math.modf(df.at[index - 1, 'Open Rank'])[0] == 0:
                    df.at[index - 1, 'Open Rank'] = df.at[index - 1, 'Open Rank'] + 0.5
                df.at[index, 'Open Rank'] = df.at[index - 1, 'Open Rank']

        counter = counter + 1

    df = df.sort_values('Tab Number')
    final_df = final_df.append(df)
    data = {'Meeting': [], 'Race': [], 'Dist': [], 'Trk Cond': [], 'Horse': [], 'Tab Number': [], 'Barrier': [],
            'Open': [], 'Open Rank': []}


# def write_sheet(meeting_name):  # Separate in sheets
#     global data, final_df
#     final_df.to_excel(writer, meeting_name, index=False)
#     final_df = pd.DataFrame()


if __name__ == "__main__":
    print('Base url = https://www.sportsbet.com.au/racing-schedule')
    print('Default date = today')
    input_url = input('Enter date (ex.: 2020-06-20): ')
    url = "https://www.sportsbet.com.au/racing-schedule/" + input_url

    if not input_url:
        input_url = datetime.today().strftime('%Y-%m-%d')

    path = os.getcwd()
    # writer = pd.ExcelWriter(path + '/' + input_url + '.xlsx', index=False)  # Separate in sheets

    start = time.time()
    australian_meetings(url)
    end = time.time()
    print(end - start)

    final_df.to_excel(path + '/' + input_url + '.xlsx', index=False)
    # writer.save()
    driver.quit()
    print('Finished scrapping.')
