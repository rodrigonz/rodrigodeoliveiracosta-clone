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
logger = logging.getLogger(__name__)
import re
import urllib2
from urllib import unquote_plus
import time

from .. import BeautifulSoup as bs
from .. import exceptions as exceptions
from ..htmlcleanup import stripHTML

from base_adapter import BaseSiteAdapter,  makeDate

ffnetgenres=["Adventure", "Angst", "Crime", "Drama", "Family", "Fantasy", "Friendship", "General",
             "Horror", "Humor", "Hurt-Comfort", "Mystery", "Parody", "Poetry", "Romance", "Sci-Fi",
             "Spiritual", "Supernatural", "Suspense", "Tragedy", "Western"]

class FanFictionNetSiteAdapter(BaseSiteAdapter):

    def __init__(self, config, url):
        BaseSiteAdapter.__init__(self, config, url)
        self.story.setMetadata('siteabbrev','ffnet')
        
        # get storyId from url--url validation guarantees second part is storyId
        self.story.setMetadata('storyId',self.parsedUrl.path.split('/',)[2])

        # normalized story URL.
        self._setURL("http://"+self.getSiteDomain()\
                         +"/s/"+self.story.getMetadata('storyId')+"/1/")

        # ffnet update emails have the latest chapter URL.
        # Frequently, when they arrive, not all the servers have the
        # latest chapter yet and going back to chapter 1 to pull the
        # chapter list doesn't get the latest.  So save and use the
        # original URL given to pull chapter list & metadata.
        self.origurl = url
        if "http://m." in self.origurl:
            ## accept m(mobile)url, but use www.
            self.origurl = self.origurl.replace("http://m.","http://www.")

    @staticmethod
    def getSiteDomain():
        return 'www.fanfiction.net'

    @classmethod
    def getAcceptDomains(cls):
        return ['www.fanfiction.net','m.fanfiction.net']

    def getSiteExampleURLs(self):
        return "http://www.fanfiction.net/s/1234/1/ http://www.fanfiction.net/s/1234/12/ http://www.fanfiction.net/s/1234/1/Story_Title"

    def getSiteURLPattern(self):
        return r"http://(www|m)?\.fanfiction\.net/s/\d+(/\d+)?(/|/[a-zA-Z0-9_-]+)?/?$"

    def extractChapterUrlsAndMetadata(self):

        # fetch the chapter.  From that we will get almost all the
        # metadata and chapter list

        url = self.origurl
        logger.debug("URL: "+url)

        # use BeautifulSoup HTML parser to make everything easier to find.
        try:
            data = self._fetchUrl(url)
            #logger.debug("\n===================\n%s\n===================\n"%data)
            soup = bs.BeautifulSoup(data)
        except urllib2.HTTPError, e:
            if e.code == 404:
                raise exceptions.StoryDoesNotExist(url)
            else:
                raise e
            
        if "Unable to locate story" in data:
            raise exceptions.StoryDoesNotExist(url)

        # some times "Chapter not found...", sometimes "Chapter text not found..."
        if "not found. Please check to see you are not using an outdated url." in data:
            raise exceptions.FailedToDownload("Error downloading Chapter: %s!  'Chapter not found. Please check to see you are not using an outdated url.'" % url)

        try:
            # rather nasty way to check for a newer chapter.  ffnet has a
            # tendency to send out update notices in email before all
            # their servers are showing the update on the first chapter.
            try:
                chapcount = len(soup.find('select', { 'name' : 'chapter' } ).findAll('option'))
            # get chapter part of url.
            except:
                chapcount = 1
            chapter = url.split('/',)[5]
            tryurl = "http://%s/s/%s/%d/"%(self.getSiteDomain(),
                                           self.story.getMetadata('storyId'),
                                           chapcount+1)
            logger.debug('=Trying newer chapter: %s' % tryurl)
            newdata = self._fetchUrl(tryurl)
            if "not found. Please check to see you are not using an outdated url." \
                    not in newdata:
                logger.debug('=======Found newer chapter: %s' % tryurl)
                soup = bs.BeautifulSoup(newdata)
        except:
            pass
        
        # Find authorid and URL from... author url.
        a = soup.find('a', href=re.compile(r"^/u/\d+"))
        self.story.setMetadata('authorId',a['href'].split('/')[2])
        self.story.setMetadata('authorUrl','http://'+self.host+a['href'])
        self.story.setMetadata('author',a.string)

        ## Pull some additional data from html.

        ## ffnet shows category two ways
        ## 1) class(Book, TV, Game,etc) >> category(Harry Potter, Sailor Moon, etc)
        ## 2) cat1_cat2_Crossover
        ## For 1, use the second link.
        ## For 2, fetch the crossover page and pull the two categories from there.

        categories = soup.findAll('a',{'class':'xcontrast_txt'})
        if len(categories) > 1:
            self.story.addToList('category',stripHTML(categories[-1]))
        elif 'Crossover' in categories[0]['href']:
            caturl = "http://%s%s"%(self.getSiteDomain(),categories[0]['href'])
            catsoup = bs.BeautifulSoup(self._fetchUrl(caturl))
            for a in catsoup.findAll('a',href=re.compile(r"^/crossovers/")):
                self.story.addToList('category',stripHTML(a))
            
        a = soup.find('a', href='http://www.fictionratings.com/')
        rating = a.string
        if 'Fiction' in rating: # if rating has 'Fiction ', strip that out for consistency with past.
            rating = rating[8:]
            
        self.story.setMetadata('rating',rating)

        # after Rating, the same bit of text containing id:123456 contains
        # Complete--if completed.
        gui_table1i = soup.find(id="gui_table1i")

        self.story.setMetadata('title', stripHTML(gui_table1i.find('b'))) # title appears to be only(or at least first) bold tag in gui_table1i

        summarydiv = gui_table1i.find('div',{'style':'margin-top:2px'})
        if summarydiv:
            self.setDescription(url,stripHTML(summarydiv))
            
        
        metatext = stripHTML(gui_table1i.find('div', {'style':'color:gray;'})).replace('Hurt/Comfort','Hurt-Comfort')
        metalist = metatext.split(" - ")
        #logger.debug("metatext:(%s)"%metalist)

        # Rated: Fiction K - English - Words: 158,078 - Published: 02-04-11

        # rating is obtained above more robustly.
        if metalist[0].startswith('Rated:'):
            metalist=metalist[1:]

        # next is assumed to be language.
        self.story.setMetadata('language',metalist[0])
        metalist=metalist[1:]

        # next might be genre.
        genrelist = metalist[0].split('/') # Hurt/Comfort already changed above.
        goodgenres=True
        for g in genrelist:
            #logger.debug("g:(%s)"%g)
            if g.strip() not in ffnetgenres:
                logger.info("g not in ffnetgenres")
                goodgenres=False
        if goodgenres:
            self.story.extendList('genre',genrelist)
            metalist=metalist[1:]

        donechars = False
        while len(metalist) > 0:
            if  metalist[0].startswith('Chapters') or metalist[0].startswith('Status') or metalist[0].startswith('id:'):
                pass
            elif  metalist[0].startswith('Reviews'):
                self.story.setMetadata('reviews',metalist[0].split(':')[1].strip())
            elif  metalist[0].startswith('Favs:'):
                self.story.setMetadata('favs',metalist[0].split(':')[1].strip())
            elif  metalist[0].startswith('Follows:'):
                self.story.setMetadata('follows',metalist[0].split(':')[1].strip())
            elif  metalist[0].startswith('Updated'):
                self.story.setMetadata('dateUpdated',makeDate(metalist[0].split(':')[1].strip(), '%m-%d-%y'))
            elif  metalist[0].startswith('Published'):
                self.story.setMetadata('datePublished',makeDate(metalist[0].split(':')[1].strip(), '%m-%d-%y'))
            elif  metalist[0].startswith('Words'):
                self.story.setMetadata('numWords',metalist[0].split(':')[1].strip())
            elif not donechars:
                self.story.extendList('characters',metalist[0].split('&'))
                donechars = True
            metalist=metalist[1:]

        # next might be characters, otherwise Reviews, Updated, Published, Words
        # if not ( metalist[0].startswith('Reviews') or metalist[0].startswith('Updated') or metalist[0].startswith('Published') or metalist[0].startswith('Words') or metalist[0].startswith('Chapters') ):
        #     self.story.extendList('characters',metalist[0].split('&'))
        
        if 'Status: Complete' in metatext:
            self.story.setMetadata('status', 'Completed')
        else:
            self.story.setMetadata('status', 'In-Progress')

        img = soup.find('img',{'class':'cimage'})
        if img:
            self.setCoverImage(url,img['src'])
            
        # Find the chapter selector 
        select = soup.find('select', { 'name' : 'chapter' } )
    	 
        if select is None:
    	   # no selector found, so it's a one-chapter story.
    	   self.chapterUrls.append((self.story.getMetadata('title'),url))
        else:
            allOptions = select.findAll('option')
            for o in allOptions:
                url = u'http://%s/s/%s/%s/' % ( self.getSiteDomain(),
                                            self.story.getMetadata('storyId'),
                                            o['value'])
                # just in case there's tags, like <i> in chapter titles.
                title = u"%s" % o
                title = re.sub(r'<[^>]+>','',title)
                self.chapterUrls.append((title,url))

        self.story.setMetadata('numChapters',len(self.chapterUrls))

        return

    def getChapterText(self, url):
        logger.debug('Getting chapter text from: %s' % url)
        time.sleep(0.5) ## ffnet(and, I assume, fpcom) tends to fail
                        ## more if hit too fast.  This is in
                        ## additional to what ever the
                        ## slow_down_sleep_time setting is.
        data = self._fetchUrl(url)

        # some ancient stories have body tags inside them that cause
        # soup parsing to discard the content.  For story text we
        # don't care about anything before "<div class='storytextp"
        # (there's a space after storytextp, so no close quote(')) and
        # this kills any body tags.
        data = data[data.index("<div class='storytextp"):]
        data.replace("<body","<notbody").replace("<BODY","<NOTBODY")
        
        soup = bs.BeautifulSoup(data)

        ## Remove the 'share' button.
        sharediv = soup.find('div', {'class' : 'a2a_kit a2a_default_style'})
        if sharediv:
            sharediv.extract()
        
        div = soup.find('div', {'id' : 'storytextp'})
        
        if None == div:
            logger.debug('div id=storytextp not found.  data:%s'%data)
            raise exceptions.FailedToDownload("Error downloading Chapter: %s!  Missing required element!" % url)

        return self.utf8FromSoup(url,div)

def getClass():
    return FanFictionNetSiteAdapter

