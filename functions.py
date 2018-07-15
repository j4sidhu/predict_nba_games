# -*- coding: utf-8 -*-
"""
Created on Wed Jan  4 22:25:01 2017

@author: Jobanjot
"""

from nba_py import constants, team, game, player
#Documentation on nba_py: 
# https://github.com/seemethere/nba_py/wiki/stats.nba.com-Endpoint-Documentation

import pandas as pd
import datetime as dt
import requests
from lxml import html

health_site = "http://espn.go.com/nba/injuries"

def get_injury_list(site):
    # Got this function from https://github.com/nfmcclure/NBA_Predictions
    page = requests.get(site)
    tree = html.fromstring(page.text)
    names_even = tree.xpath('//tr[starts-with(@class,"evenrow player")]/td/a/text()')
    names_odd = tree.xpath('//tr[starts-with(@class,"oddrow player")]/td/a/text()')
    status_even = tree.xpath('//tr[starts-with(@class,"evenrow player")]/td/following-sibling::td/text()')
    dates_even = status_even[1::2]
    status_even = status_even[0::2]
    status_odd = tree.xpath('//tr[starts-with(@class,"oddrow player")]/td/following-sibling::td/text()')
    dates_odd = status_odd[1::2]
    status_odd = status_odd[0::2]
    
    names = names_even + names_odd
    status = status_even + status_odd
    dates = dates_even + dates_odd
    
    dates = [dt.datetime.strptime(date + str(dt.date.today().year), 
                                  '%b %d%Y').date() 
                                    for date in dates]
    # This might fail around the new year
    
    injury_frame = pd.DataFrame({'name': names,
                                 'player_status': status,
                                 'date': dates})
    
    injury_frame = injury_frame[injury_frame['date'] == max(dates)]
    # Only get the injury list for the most recent date
    
    injury_frame.drop_duplicates(subset='name', inplace=True)
    injury_frame.reset_index(inplace=True, drop=True)
    return injury_frame

injuries = get_injury_list(health_site)
serious_injuries = injuries[injuries['player_status'] != 'Day-To-Day']
soft_injuries = injuries[injuries['player_status'] == 'Day-To-Day']

class nba_game_simulation:
    
    def __init__(self, home_team, away_team):
        assert home_team in constants.TEAMS.keys()
        assert away_team in constants.TEAMS.keys()
        
        self.home_team = home_team
        self.home_team_id = constants.TEAMS[home_team]['id']
        roster1 = team.TeamCommonRoster(self.home_team_id).roster()
        roster1['Strength'] = 1 # Everyone is at full strength
        roster1.loc[roster1['PLAYER'].isin(serious_injuries['name'].tolist()), 'Strength'] = 0
        roster1.loc[roster1['PLAYER'].isin(soft_injuries['name'].tolist()), 'Strength'] = 0.5
        #roster1['Points'] = None
        #roster1['Mins'] = None
        
        self.home_roster = roster1
        
        self.away_team = away_team
        self.away_team_id = constants.TEAMS[away_team]['id']
        roster2 = team.TeamCommonRoster(self.away_team_id).roster()
        
        roster2['Strength'] = 1 # Everyone is at full strength to begin with
        roster2.loc[roster2['PLAYER'].isin(serious_injuries['name'].tolist()), 'Strength'] = 0
        roster2.loc[roster2['PLAYER'].isin(soft_injuries['name'].tolist()), 'Strength'] = 0.5
        #roster2['Points'] = None
        #roster2['Mins'] = None
        
        self.away_roster = roster2
        
    def play_game(self):
        
        self.get_mins()
        self.get_points() 
        # Updates the points in self.home_roster and self.away_roster
        
        self.total_home_pts = int(round(sum(self.home_roster['Points'].tolist())))
        self.total_away_pts = int(round(sum(self.away_roster['Points'].tolist())))
        
        if self.total_home_pts >= self.total_away_pts:
            print ("{0} won. Score: {0} {1} - {2} {3}".format(self.home_team, 
                           self.total_home_pts, self.away_team, 
                           self.total_away_pts))
        else:
            print ("{0} won. Score: {0} {1} - {2} {3}".format(self.away_team, 
               self.total_away_pts, self.home_team, self.total_home_pts))
    
    def get_mins(self):
        
        for index, playerrow in self.home_roster.iterrows():
            player_id = playerrow['PLAYER_ID']
            all_season_stats = player.PlayerCareer(player_id).regular_season_totals()
            current_season_stats = all_season_stats[(all_season_stats['SEASON_ID'] == 
                                                     constants.CURRENT_SEASON)]
            season_mins = (current_season_stats[current_season_stats['SEASON_ID'] == 
                                                constants.CURRENT_SEASON]['MIN'])
            if len(season_mins) == 0:
                mins = 0
            else:
                mins = season_mins.tolist()[0]
            
            self.home_roster.set_value(index, 'Mins', mins)
        
        all_mins = sorted(self.home_roster[self.home_roster['Strength'] != 
                                0]['Mins'].tolist(), reverse=True)
        if len(all_mins) >= 12:
            # If there are too many guys, set the guys with the lowest mins to 0
            self.home_roster.loc[self.home_roster['Mins'] < all_mins[11], 'Strength'] = 0
            
        for index, playerrow in self.away_roster.iterrows():
            player_id = playerrow['PLAYER_ID']
            all_season_stats = player.PlayerCareer(player_id).regular_season_totals()
            current_season_stats = all_season_stats[(all_season_stats['SEASON_ID'] == 
                                                     constants.CURRENT_SEASON)]
            season_mins = (current_season_stats[current_season_stats['SEASON_ID'] == 
                                                constants.CURRENT_SEASON]['MIN'])
            if len(season_mins) == 0:
                mins = 0
            else:
                mins = season_mins.tolist()[0]
            
            self.away_roster.set_value(index, 'Mins', mins)
        
        all_mins = sorted(self.away_roster[self.away_roster['Strength'] != 
                                0]['Mins'].tolist(), reverse=True)
        if len(all_mins) >= 12:
            # Only want the first 12 guys
            # If there are too many guys, set the guys with the lowest mins to 0
            self.away_roster.loc[self.away_roster['Mins'] < all_mins[11], 'Strength'] = 0

    def get_points(self):
        
        for index, playerrow in self.home_roster.iterrows():
            player_id = playerrow['PLAYER_ID']
            player_strength = playerrow['Strength']
            full_stats = player.PlayerSummary(player_id).headline_stats()
            current_season_stats = (full_stats[full_stats['TimeFrame'] == 
                                 constants.CURRENT_SEASON]['PTS'])
            if len(current_season_stats) == 0:
                points = 0
            else:
                points = current_season_stats.tolist()[0]*player_strength
                
            self.home_roster.set_value(index, 'Points', points)
        
        for index, playerrow in self.away_roster.iterrows():
            player_id = playerrow['PLAYER_ID']
            player_strength = playerrow['Strength']
            full_stats = player.PlayerSummary(player_id).headline_stats()
            current_season_stats = (full_stats[full_stats['TimeFrame'] == 
                                 constants.CURRENT_SEASON]['PTS'])
            if len(current_season_stats) == 0:
                points = 0
            else:
                points = current_season_stats.tolist()[0]*player_strength

            self.away_roster.set_value(index, 'Points', points)
            
    def get_points1(self, roster):
        player_pts = {}
        for index, playerrow in roster.iterrows():
            player_id = playerrow['PLAYER_ID']
            player_strength = playerrow['Strength']
            player_pts[player_id] = (player.PlayerSummary(player_id)
                                        .headline_stats()['PTS'][0])*player_strength
        return player_pts
        
a = nba_game_simulation('TOR', 'ATL').play_game()