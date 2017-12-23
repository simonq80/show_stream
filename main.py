from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import re
import urllib.parse
from dateutil.parser import parse as dateparse


db_path = 'mysql+pymysql://root:mysql@localhost:32775/db1'
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def fetch_nyaa(search, user):
    search = urllib.parse.quote(search)
    user = urllib.parse.quote(user)
    ss = 'https://nyaa.si/user/{}?f=0&c=0_0&q={}'
    req = ss.format(user, search)
    data = requests.get(req).text
    s = BeautifulSoup(data)
    table = s.find('table', class_='torrent-list')
    rows = table.tbody.findAll('tr')
    episodes = []
    for row in rows:
        cells = row.findAll('td')
        try:
            link = cells[1].findAll('a')
            lstr = ''
            for l in link:
                if 'comment' not in l.get('title'):
                    lstr = l.string
            magnet = cells[2].find('a', href=re.compile('magnet:?'))
            date = dateparse(cells[4].string)
            episodes.append(
                {
                    'name': lstr,
                    'link': magnet.get('href'),
                    'date': date
                }
            )
        except:
            pass
    return episodes


site_methods = {
    'nyaa.si': fetch_nyaa
}

def fetch_episodes(site, search, user=None):
    m = site_methods.get(site)
    if m is None:
        return None
    return m(search, user)




class show(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    site = db.Column(db.String(80), nullable=False)
    search = db.Column(db.String(80), nullable=False)
    user = db.Column(db.String(80), nullable=False)

    @staticmethod
    def add_show():
        return None

    def get_episodes(self):
        current_eps = [e.name for e in self.episodes]
        eps = fetch_episodes(self.site, self.search, self.user)

        for ep in eps:
            if(ep['name'] not in current_eps):
                e = episode(name=ep['name'], link=ep['link'], date=ep['date'], watched=False)

                self.episodes.append(e)
        print(self)
        db.session.add(self)

    def __repr__(self):
        return self.name + self.site + self.search + self.user + str([e.name for e in self.episodes])



class episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    link = db.Column(db.String(500), nullable=False)
    date = db.Column(db.DateTime)
    show_id = db.Column(db.Integer, db.ForeignKey('show.id'),
        nullable=False)
    show = db.relationship('show', backref=db.backref('episodes', lazy=True))
    watched = db.Column(db.Boolean)

    def __repr__(self):
        return '{} {} {} {}'.format(self.name, self.link, str(self.date), str(self.watched))

@app.route('/')
def d(name=None, remove=None):
    shows = db.session.query(show).all()
    n= str(len(shows))
    s = show(name=('show' + n), search_string=('http://show/' + n))
    for i in range(0, len(shows)):
        s.episodes.append(episode(name=('episode'+n+str(i)), date=datetime.now(),watched=False))
    db.session.add(s)
    db.session.commit()
    return str([[(e.name, e.watched) for e in s.episodes] for s in shows])

def new_episodes(show_name):
    pass

@app.route('/add_show', methods=['GET'])
def add_show():
    show_name = 'Imouto1234'
    site = 'nyaa.si'
    search = 'Imouto sa [1080p]'
    user = 'HorribleSubs'

    s = show(name=show_name, site=site, search=search, user=user)
    s.get_episodes()
    db.session.commit()
    return 'asdf'

@app.route('/ad', methods=['GET'])
def add_how():
    dev = db.session.query(show).all()
    print([d.name for d in dev])
    return 'asd'





if __name__ == "__main__":
    db.create_all()
    app.run(host='0.0.0.0', port=8000)
