from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import re
import urllib.parse


db_path = 'mysql+pymysql://root:mysql@localhost:32775/db1'
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def fetch_nyaa(search, user):
    search = [urllib.parse.quote(s) for s in search]
    user = urllib.parse.quote(user)
    ss = 'https://nyaa.si/user/{}?f=0&c=0_0&q={}'
    req = ss.format(user, '+'.join(search))
    data = requests.get(req).text
    s = BeautifulSoup(data)
    table = s.find('table', class_='torrent-list')
    rows = table.tbody.findAll('tr')
    for row in rows:
        cells = row.findAll('td')
        try:
            link = cells[1].findAll('a')
            lstr = ''
            for l in link:
                if 'comment' not in l.get('title'):
                    lstr = l.string
            magnet = cells[2].find('a', href=re.compile('magnet:?'))
            print(lstr)
            print(magnet.get('href'))
        except:
            pass

    return None


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
    search_string = db.Column(db.String(300), unique=True, nullable=False)

    @staticmethod
    def add_show(searchurl):
        return None


class episode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    date = db.Column(db.DateTime)
    show_id = db.Column(db.Integer, db.ForeignKey('show.id'),
        nullable=False)
    show = db.relationship('show', backref=db.backref('episodes', lazy=True))
    watched = db.Column(db.Boolean)

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




if __name__ == "__main__":
    db.create_all()
    app.run(host='0.0.0.0', port=8000)
