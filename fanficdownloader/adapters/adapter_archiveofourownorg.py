# -*- coding: utf-8 -*-

# Copyright 2011 Fanficdownloader team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import time
import logging
import re
import urllib2

from .. import BeautifulSoup as bs
from ..htmlcleanup import stripHTML
from .. import exceptions as exceptions

from base_adapter import BaseSiteAdapter, utf8FromSoup, makeDate

def getClass():
    return ArchiveOfOurOwnOrgAdapter


class ArchiveOfOurOwnOrgAdapter(BaseSiteAdapter):

    def __init__(self, config, url):
        BaseSiteAdapter.__init__(self, config, url)

        self.decode = ["utf8",
                       "Windows-1252"] # 1252 is a superset of iso-8859-1.
                               # Most sites that claim to be
                               # iso-8859-1 (and some that claim to be
                               # utf8) are really windows-1252.
							   
							   
        
        # get storyId from url--url validation guarantees query is only sid=1234
        self.story.setMetadata('storyId',self.parsedUrl.path.split('/',)[2])
        logging.debug("storyId: (%s)"%self.story.getMetadata('storyId'))
        
        # normalized story URL.
        self._setURL('http://' + self.getSiteDomain() + '/works/'+self.story.getMetadata('storyId'))
        
        # Each adapter needs to have a unique site abbreviation.
        self.story.setMetadata('siteabbrev','ao3')

        # The date format will vary from site to site.
        # http://docs.python.org/library/datetime.html#strftime-strptime-behavior
        self.dateformat = "%Y-%b-%d"
            
    @staticmethod # must be @staticmethod, don't remove it.
    def getSiteDomain():
        # The site domain.  Does have www here, if it uses it.
        return 'www.archiveofourown.org'

    def getSiteExampleURLs(self):
        return "http://"+self.getSiteDomain()+"/works/123456"

    def getSiteURLPattern(self):
        return re.escape("http://"+self.getSiteDomain()+"/works/")+r"\d+(/chapters/\d+)?/?$"

    ## Getting the chapter list and the meta data, plus 'is adult' checking.
    def extractChapterUrlsAndMetadata(self):

        if self.is_adult or self.getConfig("is_adult"):
            addurl = "?view_adult=true"
        else:
            addurl=""

        meta = self.url+addurl
        url = self.url+'/navigate'+addurl
        logging.debug("URL: "+meta)

        try:
            data = self._fetchUrl(url)
            meta = self._fetchUrl(meta)
        except urllib2.HTTPError, e:
            if e.code == 404:
                raise exceptions.StoryDoesNotExist(self.meta)
            else:
                raise e
            
        # use BeautifulSoup HTML parser to make everything easier to find.
        soup = bs.BeautifulSoup(data)
        metasoup = bs.BeautifulSoup(meta)
        # print data

        # Now go hunting for all the meta data and the chapter list.
        
        ## Title
        a = soup.find('a', href=re.compile(r"^/works/\w+"))
        self.story.setMetadata('title',a.string)
		
        # Find authorid and URL from... author url.
        a = soup.find('a', href=re.compile(r"^/users/\w+/pseuds/\w+"))
        self.story.setMetadata('authorId',a['href'].split('/')[2])
        self.story.setMetadata('authorUrl','http://'+self.host+a['href'])
        self.story.setMetadata('author',a.text)

        # Find the chapters:
        chapters=soup.findAll('a', href=re.compile(r'/works/'+self.story.getMetadata('storyId')+"/chapters/\d+$"))
        self.story.setMetadata('numChapters',len(chapters))
        logging.debug("numChapters: (%s)"%self.story.getMetadata('numChapters'))
        for x in range(0,len(chapters)):
            # just in case there's tags, like <i> in chapter titles.
            chapter=chapters[x]
            if len(chapters)==1:
                self.chapterUrls.append((self.story.getMetadata('title'),'http://'+self.host+chapter['href']+addurl))
            else:
                self.chapterUrls.append((stripHTML(chapter),'http://'+self.host+chapter['href']+addurl))



        a = metasoup.find('blockquote',{'class':'userstuff'})
        if a != None:
            self.story.setMetadata('description',a.text)
		
        a = metasoup.find('dd',{'class':"rating tags"})
        if a != None:
            self.story.setMetadata('rating',stripHTML(a.text))
		
        a = metasoup.find('dd',{'class':"fandom tags"})
        fandoms = a.findAll('a',{'class':"tag"})
        fandomstext = [fandom.string for fandom in fandoms]
        for fandom in fandomstext:
            self.story.addToList('category',fandom.string)
		
        a = metasoup.find('dd',{'class':"warning tags"})
        if a != None:
            warnings = a.findAll('a',{'class':"tag"})
            warningstext = [warning.string for warning in warnings]
            for warning in warningstext:
                if warning.string == "Author Chose Not To Use Archive Warnings":
                    warning.string = "No Archive Warnings Apply"
                if warning.string != "No Archive Warnings Apply":
                    self.story.addToList('warnings',warning.string)
		
        a = metasoup.find('dd',{'class':"freeform tags"})
        if a != None:
            genres = a.findAll('a',{'class':"tag"})
            genrestext = [genre.string for genre in genres]
            for genre in genrestext:
                self.story.addToList('genre',genre.string)
        a = metasoup.find('dd',{'class':"category tags"})
        if a != None:
            genres = a.findAll('a',{'class':"tag"})
            genrestext = [genre.string for genre in genres]
            for genre in genrestext:
                if genre != "Gen":
                    self.story.addToList('genre',genre.string)
		
        a = metasoup.find('dd',{'class':"character tags"})
        if a != None:
            chars = a.findAll('a',{'class':"tag"})
            charstext = [char.string for char in chars]
            for char in charstext:
                self.story.addToList('characters',char.string)
        a = metasoup.find('dd',{'class':"relationship tags"})
        if a != None:
            chars = a.findAll('a',{'class':"tag"})
            charstext = [char.string for char in chars]
            for char in charstext:
                self.story.addToList('characters',char.string)
		

        stats = metasoup.find('dl',{'class':'stats'})
        dt = stats.findAll('dt')
        dd = stats.findAll('dd')
        for x in range(0,len(dt)):
            label = dt[x].text
            value = dd[x].text

            if 'Words:' in label:
                self.story.setMetadata('numWords', value)
				
            if 'Chapters:' in label:
                if value.split('/')[0] == value.split('/')[1]:
                    self.story.setMetadata('status', 'Completed')
                else:
                    self.story.setMetadata('status', 'In-Progress')


            if 'Published' in label:
                self.story.setMetadata('datePublished', makeDate(stripHTML(value), self.dateformat))
                self.story.setMetadata('dateUpdated', makeDate(stripHTML(value), self.dateformat))
            
            if 'Updated' in label:
                self.story.setMetadata('dateUpdated', makeDate(stripHTML(value), self.dateformat))
				
            if 'Completed' in label:
                self.story.setMetadata('dateUpdated', makeDate(stripHTML(value), self.dateformat))

		
        try:
            # Find Series name from series URL.
            a = metasoup.find('dd',{'class':"series"})
            b = a.find('a', href=re.compile(r"/series/\d+"))
            series_name = b.string
            series_url = 'http://'+self.host+'/fanfic/'+b['href']
            series_index = int(a.text.split(' ')[1])
            self.setSeries(series_name, series_index)
            
        except:
            # I find it hard to care if the series parsing fails
            pass

    # grab the text for an individual chapter.
    def getChapterText(self, url):
        logging.debug('Getting chapter text from: %s' % url)
		
        chapter=bs.BeautifulSoup('<div class="story"></div>')
        soup = bs.BeautifulSoup(self._fetchUrl(url),selfClosingTags=('br','hr'))
		
        headnotes = soup.find('div', {'class' : "preface group"}).find('div', {'class' : "notes module"})
        if headnotes != None:
            headnotes = headnotes.find('blockquote', {'class' : "userstuff"})
            if headnotes != None:
                chapter.append(bs.BeautifulSoup("<b>Author's Note:</b>"))
                chapter.append(headnotes)
			
        chapsumm = soup.find('div', {'id' : "summary"})
        if chapsumm != None:
            chapsumm = chapsumm.find('blockquote')
            chapter.append(bs.BeautifulSoup("<b>Summary for the Chapter:</b>"))
            chapter.append(chapsumm)
        chapnotes = soup.find('div', {'id' : "notes"})
        if chapnotes != None:
            chapnotes = chapnotes.find('blockquote')
            chapter.append(bs.BeautifulSoup("<b>Notes for the Chapter:</b>"))
            chapter.append(chapnotes)
			
        footnotes = soup.find('div', {'id' : "work_endnotes"})
		
        soup = soup.find('div', {'class' : "userstuff module"})
        chtext = soup.find('h3', {'class' : "landmark heading"})
        if chtext:
            chtext.extract()
        chapter.append(soup)
		
        if footnotes != None:
            footnotes = footnotes.find('blockquote')
            chapter.append(bs.BeautifulSoup("<b>Author's Note:</b>"))
            chapter.append(footnotes)
			
        if None == soup:
            raise exceptions.FailedToDownload("Error downloading Chapter: %s!  Missing required element!" % url)
    
        return utf8FromSoup(chapter)
