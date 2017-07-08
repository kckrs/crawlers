# -*- coding: utf-8 -*-
from dateutil.parser import parse
from urlparse import urlparse
import scrapy

class GoalComSpider(scrapy.Spider):
    name = 'goal.com'
    allowed_domains = ['goal.com']
    start_urls = ['http://www.goal.com/en-us/tables/']

    def parse(self, response):
        test_xpath = '//table[@data-area-id="5"]/caption/a[@href="/en-us/tables/copa-libertadores/241"]/@href'
        full_xpath = '//table[@class="short"]/caption/a/@href'
        xpath = full_xpath

        for league_url in response.xpath(xpath).extract():
            league_url = response.urljoin(league_url)
            request = scrapy.Request(url=league_url, callback=self.parse_league)
            league_id = id_from_url(league_url, 'league')
            request.meta['league_id'] = league_id
            yield request

    def parse_league(self, response):
        league_id = response.meta['league_id']
        league = {
            'type': 'league',
            'name': response.xpath('//header/h1/text()').extract_first(),
            'goal_id': league_id,
            'goal_url': response.url
        }

        # retrieve all the teams in the league
        test_xpath = '//table[@class="short"]/tbody[1]/tr[1]/td[4]/a/@href'
        full_xpath = '//td[@class="legend team full"]/a/@href'
        xpath = full_xpath

        for team_url in response.xpath(xpath).extract():
            team_url = response.urljoin(team_url)
            team_id = id_from_url(team_url, 'team')

            yield {
                'type': 'league_team',
                'league_id': league_id,
                'team_id': team_id
            }

            request = scrapy.Request(url=team_url, callback=self.parse_team)
            request.meta['team_id'] = team_id
            yield request

        yield league

    def parse_team(self, response):
        team_id = response.meta['team_id']
        team = {
            'type': 'team',
            'name': response.xpath('//section[@class="team-badge"]//span[@class="team-name"]/text()').extract_first(),
            'img_src': response.xpath('//section[@class="team-badge"]//span[@class="badge"]/img/@src').extract_first(),
            'goal_id': team_id,
            'goal_url': response.url
        }

        # retrieve all the players on the team
        test_xpath = '//table[@class="tab-squad tab-squad-players"]//tr[1]/td[@class="name"]/a/@href'
        full_xpath = '//table[@class="tab-squad tab-squad-players"]//td[@class="name"]/a/@href'
        xpath = full_xpath

        for player_url in response.xpath(xpath).extract():
            # skip players without a url / id
            if player_url == '':
                continue

            player_url = response.urljoin(player_url)
            player_id = id_from_url(player_url, 'player')

            yield {
                'type': 'team_player',
                'team_id': team_id,
                'player_id': player_id
            }

            request = scrapy.Request(url=player_url, callback=self.parse_player)
            request.meta['player_id'] = player_id
            yield request

        yield team

    def parse_player(self, response):
        player_id = response.meta['player_id']
        player = {
            'type': 'player',
            'name': response.xpath('//div[@id="playerStatsCard"]//tr/td[@class="playerName"]/text()').extract_first(),
            'img_src': response.xpath('//img[@id="playerProfilePhoto"]/@src').extract_first(),
            'goal_id': player_id,
            'goal_url': response.url
        }

        # don't bring in dummy player images
        if player['img_src'].find('images/default/dummy/goal.news.jpg') > -1:
            player['img_src'] = ''

        # extract the stat table
        statLabels = response.xpath('//div[@id="playerStatsCard"]//tr/td[1]').extract()
        statValues = response.xpath('//div[@id="playerStatsCard"]//tr/td[2]').extract()

        # make sure the labels and values are parallel
        if len(statLabels) != len(statValues):
            raise NameError('bad player stats table')

        for i in range(len(statLabels)):
             # skip the main player name row
            if statLabels[i].find('class="playerName"') > -1:
                continue

            # eliminate <td>
            statLabels[i] = statLabels[i][28:len(statLabels[i])-5].strip(':')
            statValues[i] = statValues[i][28:len(statValues[i])-5]

            # process the data individually
            if statLabels[i] == 'Full Name':
                player['fullname'] = statValues[i]
            
            elif statLabels[i] == 'Nickname':
                player['nickname'] = statValues[i]
            
            elif statLabels[i] == 'Date of Birth':
                idx = statValues[i].find('(')
                if idx > -1:
                    statValues[i] = statValues[i][:idx-1]
                
                try:
                    player['birthdate'] = parse(statValues[i])
                except ValueError: 
                    pass

            elif statLabels[i] == 'Place of Birth':
                player['birthplace'] = statValues[i]
            
            elif statLabels[i] == 'Nationality':
                player['nationality'] = statValues[i]
            
            elif statLabels[i] == 'Height':
                idx = statValues[i].lower().find('cm')
                if idx > -1:
                    statValues[i] = statValues[i][:idx-1]
                player['height'] = int(statValues[i])
            
            elif statLabels[i] == 'Weight':
                idx = statValues[i].lower().find('kg')
                if idx > -1:
                    statValues[i] = statValues[i][:idx-1]
                player['weight'] = int(statValues[i])
            
            elif statLabels[i] == 'Position':
                player['position'] = statValues[i]
            
            elif statLabels[i] == 'Squad Number':
                player['squadnum'] = statValues[i]
            
            elif statLabels[i] == 'National Team Page':
                player['national_team'] = statValues[i]

            else:
                raise NameError('unknown label in stats table: ' + statLabels[i])

        yield player

# Function definition is here
def id_from_url( url, url_type ):
    u = urlparse(url)
    paths = u.path.strip('/').split('/')

    pathoffset = 1
    if url_type == 'player':
        pathoffset = 2

    id = paths[len(paths)-pathoffset]
    return int(id)