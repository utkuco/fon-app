import queue
import requests
from lxml import html
from lxml import etree
import datetime
import time
import json
from threading import Thread
from datetime import date, timedelta
import os
import click

documentsWithAttachmentQueue = queue.Queue()
downloadPdfUrlsQueue = queue.Queue()


class ThreadGetURLs(Thread):
    """Threaded PDF Url Grab"""

    def __init__(self, documentsWithAttachmentQueue, downloadPdfUrlsQueue, start_date, end_date):
        Thread.__init__(self)
        self.documentsWithAttachmentQueue = documentsWithAttachmentQueue
        self.downloadPdfUrlsQueue = downloadPdfUrlsQueue
        self.documentsByDateDictionary = dict()
        self.base_API = 'https://www.kap.org.tr/en/api/disclosures?disclosureTypes=FR-ODA-DUY-DG&fromDate={}&toDate={}&memberTypes=IGS-YK-PYS-DDK-DG'.format(
            start_date, end_date)
        self.start_date = start_date
        self.end_date = end_date

    def getAllDocuments(self):
        numberOfAttachments = 0
        try:
            response = requests.get(self.base_API)
            data = json.loads(response.text)

            for d in data:
                attachmentCount = d.get('basic').get('attachmentCount')
                publishDate, publishTime = d.get('basic').get('publishDate').split(" ")

                if (publishDate not in self.documentsByDateDictionary):
                    self.documentsByDateDictionary[publishDate] = {'withAttachment': [], 'withoutAttachments': []}

                disclosureIndex = d.get('basic').get('disclosureIndex')

                #Add pdf url for generated PDF file of the announcment
                link = 'https://www.kap.org.tr/tr/BildirimPdf/'+str(disclosureIndex)
                self.downloadPdfUrlsQueue.put({'url':link,'directory':(publishDate + '/' + str(disclosureIndex)),'fileName': (str(disclosureIndex)+'.pdf')})


                if attachmentCount > 0:
                    numberOfAttachments += attachmentCount
                    link = "https://www.kap.org.tr/en/Bildirim/" + str(disclosureIndex)
                    self.documentsWithAttachmentQueue.put(
                        {'url': link, 'directory': (publishDate + '/' + str(disclosureIndex))})

            return numberOfAttachments
        except Exception as e:
            click.echo("API CALL ERROR!")
            click.echo(e)
            raise e

    def getLinks(self, page):
        click.echo("Scraping pdf urls from: {}".format(page['url']))
        response = requests.get(page['url'], allow_redirects=False)  # get page data from server, block redirects
        sourceCode = response.content  # get string of source code from response

        htmlElem = html.document_fromstring(sourceCode)  # make HTML element object
        elements = htmlElem.xpath(
            "//a[contains(@class,'modal-attachment')]")  # get all a tags with class modal-attachment

        for elem in elements:
            fileName = elem.text
            link = 'https://www.kap.org.tr' + elem.get('href')
            self.downloadPdfUrlsQueue.put({'url': link, 'directory': page['directory'], 'fileName': fileName})

    def run(self):
        click.echo("Started scraping pdf attachments for: {}".format(self.start_date))
        numberOfAttachments = self.getAllDocuments()  # fill queue with documents with attachment and fill queue with pdf urls
        while True:
            # time.sleep(5) # trying to avoid to be blocked by server
            try:
                documentWithAttachment = self.documentsWithAttachmentQueue.get(block=False)
                self.getLinks(documentWithAttachment)  # scraping all pdf urls from document with attachment
                self.documentsWithAttachmentQueue.task_done()
            except:
                break
        if numberOfAttachments >0:
            click.echo("For {} successfully scraped {} of pdf attachments!".format(self.start_date,numberOfAttachments))


class DownloadThread(Thread):
    """Threaded PDF Download"""
    downloadable = True
    counter = 0

    def __init__(self, downloadPdfUrlsQueue, path):
        Thread.__init__(self)
        self.downloadPdfUrlsQueue = downloadPdfUrlsQueue
        self.basePath = path

    def downloadFile(self, link, fileName, path):
        try:
            if not os.path.exists(path):
                os.makedirs(path)
            downloadFile = path + "/" + fileName
            response = requests.get(link, allow_redirects=False)

            with open(downloadFile, "wb") as myPdfFile:
                myPdfFile.write(response.content)

        except Exception as e:
            raise e

    def run(self):

        while True:
            if (not DownloadThread.downloadable):
                time.sleep(1)
                continue

            try:
                DownloadThread.counter += 1
                time.sleep(1)  # trying to avoid to be blocked by server
                document = self.downloadPdfUrlsQueue.get(block=False)
                click.echo("\nStarted downloading from : {}".format(document['url']))
                self.downloadFile(document['url'], document['fileName'], self.basePath + '/' + document['directory'])
                if (DownloadThread.counter > 0 and DownloadThread.counter % 20 == 0):
                    click.echo("After every 20 downloads wait for 2 minutes to avoid blockade!")
                    DownloadThread.downloadable = False
                    time.sleep(120)
                    DownloadThread.downloadable = True
                self.downloadPdfUrlsQueue.task_done()
                click.echo("Successfully downloaded to: {}".format(
                    self.basePath + '/' + document['directory'] + '/' + document['fileName']))


            except queue.Empty:
                return
            except Exception as e:
                click.echo(e)
                click.echo("Wait for 2 minutes")
                time.sleep(120)
                click.echo(document)
                self.downloadPdfUrlsQueue.put(document)
                self.run()


def start_download(start_date, end_date, path):
    delta = end_date - start_date

    threads = [] #scraping threads
    for i in range(delta.days + 1):
        d = start_date + timedelta(days=i)
        t = ThreadGetURLs(documentsWithAttachmentQueue, downloadPdfUrlsQueue, d, d)
        t.setDaemon(True)
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    downloadThreads = [] #downloading threads
    for i in range(1): #with more than one download thread probably downloading  will be blocked
        dt = DownloadThread(downloadPdfUrlsQueue, path)
        dt.setDaemon(True)
        dt.start()
        downloadThreads.append(dt)

    for dt in downloadThreads:
        dt.join()
