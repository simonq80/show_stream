from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import re
import urllib.parse
from dateutil.parser import parse as dateparse
from threading import Thread
from time import sleep
import configparser


c = configparser.ConfigParser()
c.read('config.cfg')
c = c['MAIN']
db_path = 'mysql+pymysql://{}:{}@{}:{}/{}'.format(c['MYSQL_USER'],
    c['MYSQL_PASS'], c['MYSQL_HOST'], c['MYSQL_PORT'], c['MYSQL_DB'])
server_host = c['SERVER_HOST']
server_port = c['SERVER_PORT']
nyaa_host = c['NYAA_HOST']


# db_path = 'mysql+pymysql://root:mysql@localhost:32775/db1'
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def fetch_nyaa(search, user):
    search = urllib.parse.quote(search)
    user = urllib.parse.quote(user)
    ss = 'https://{}/user/{}?f=0&c=0_0&q={}'
    req = ss.format(nyaa_host, user, search)
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
    'nyaa': fetch_nyaa
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
        db.session.add(self)
        db.session.commit()

    def get_next_episode(self):
        eps = [[e.name, e.link, e.date] for e in self.episodes if e.watched == False]
        mi = ['No New Episode', '' , datetime.now()]
        for e in eps:
            if e[2] < mi[2]:
                mi = e
        return mi

    def delete(self):
        for ep in self.episodes:
            db.session.delete(ep)
        db.session.commit()
        db.session.delete(self)
        db.session.commit()

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
def m():
    s = db.session.query(show).all()
    shows = [[sh.name, sh.id, sh.get_next_episode()[0]] for sh in s]
    return render_template('main.html', shows=shows)

@app.route('/add_show', methods=['GET', 'POST'])
def add_how():
    message = False
    message_string = ''
    if request.method == "POST":
        message = True
        try:
            s = show(name=request.form["sname"], site=request.form["site"], search=request.form["sstring"], user=request.form["uploader"])
            s.get_episodes()
            message_string = 'Show Added'
        except:
            message_string = 'Something Went wrong'


    return render_template('add_show.html', message=message, message_string=message_string)

@app.route('/show/<show_id>')
def show_info(show_id):
    s = db.session.query(show).filter(show.id == show_id).one_or_none()
    if not s:
        return 'show not found'
    eps = [[e.name, e.date, e.id, e.watched] for e in s.episodes]
    eps = sorted(eps, key=lambda ep: ep[1])

    return render_template('show.html', name=s.name, sid=s.id, eps=eps[::-1])


@app.route('/download_next/<show_id>')
def download(show_id):
    s = db.session.query(show).filter(show.id == show_id).one_or_none()
    if not s:
        return 'show not found'
    next_ep = s.get_next_episode()
    ep = db.session.query(episode).filter(episode.name == next_ep[0]).one_or_none()
    if ep:
        ep.watched = True
        db.session.add(ep)
        db.session.commit()
    return redirect(next_ep[1], code=302)

@app.route('/download_ep/<ep_id>')
def download_ep(ep_id):
    ep = db.session.query(episode).filter(episode.id == ep_id).one_or_none()
    if ep:
        return redirect(ep.link, code=302)
    return ''

@app.route('/watch_ep/<ep_id>')
def watch_ep(ep_id):
    ep = db.session.query(episode).filter(episode.id == ep_id).one_or_none()
    if ep:
        ep.watched = not ep.watched
        db.session.add(ep)
        db.session.commit()
    return redirect('/show/' + str(ep.show_id), code=302)

@app.route('/delete_show/<show_id>')
def delete_show(show_id):
    s = db.session.query(show).filter(show.id == show_id).one_or_none()
    if s:
        s.delete()
    return redirect('/', code=302)

@app.route('/update_shows')
def update_shows():
    s = db.session.query(show).all()
    for sh in s:
        try:
            sh.get_episodes()
        except:
            pass
    return 'success'


def show_updater():
    while True:
        sleep(1200)
        requests.get('http://{}:{}/update_shows'.format(server_host, server_port))






if __name__ == "__main__":
    db.create_all()
    thread = Thread(target=show_updater)
    thread.start()
    app.run(host=server_host, port=int(server_port))
