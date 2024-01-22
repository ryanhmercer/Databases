
"""
Columbia's COMS W4111.001 Introduction to Databases
Thilina Balasooriya and Ryan Huang
Hospital Recommendation System
To run locally:
    python3 proj1part3.py
"""
import os
from datetime import datetime
  # accessible as a variable in index.html:

from sqlalchemy import *
from flask import Flask, request, render_template, g, redirect, Response, abort
import geocoder
import geopy.distance as D

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

curr_id = -1
DATABASEURI = "postgresql://rh3129:192778@34.74.171.121/proj1part2"
engine = create_engine(DATABASEURI)
conn = engine.connect()

#find current emp_id number when running
max_emp = 0
emps_cursor = conn.execute(text("SELECT MAX(employee_id) FROM employee"))
conn.commit()
emps = []
for result in emps_cursor:
  emps.append(result[0])
max_emp = emps[0]

@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request.

  The variable g is globally accessible.
  """
  try:
    g.conn = engine.connect()
  except:
    print("uh oh, problem connecting to database")
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't, the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass

@app.route('/')
def index(str=''):
  global curr_id
  curr_id = -1

  context = dict(str=str)
  """
  request is a special object that Flask provides to access web request information:

  request.method:   "GET" or "POST"
  request.form:     if the browser submitted a form, this contains the data in the form
  request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

  See its API: https://flask.palletsprojects.com/en/2.0.x/api/?highlight=incoming%20request%20data

  """

  return render_template("index.html", **context)

#

def gen_content():
  global curr_id
  id = curr_id
  cursor = g.conn.execute(text(f'SELECT E.name FROM employee E WHERE E.employee_id = {id}'))
  g.conn.commit()

  names = []
  for result in cursor:
    names.append(result[0])

  return names[0]

@app.route('/another', methods=['POST'])
def another():
  name = gen_content()
  context = dict(name=name)
  return render_template("another.html", **context)

@app.route('/back', methods=['POST'])
def back():
  global curr_id
  if curr_id == -1:
    return redirect('/')
  else:
    return another()

##Admin Screen Options
@app.route('/rec', methods=['POST', 'GET'])
def rec(str='', has_rec = False, data = []):
  context = dict(str=str, has_rec = has_rec, data=data)
  return render_template("patient.html", **context)

def get_distance(addr1, addr2):
  c = geocoder.google(addr1, key='AIzaSyCaDyC-91w6O-rOZcA-YXJin_9WJJBRlYw')
  t = geocoder.google(addr2, key='AIzaSyCaDyC-91w6O-rOZcA-YXJin_9WJJBRlYw')
  return D.geodesic(c.latlng, t.latlng).miles

def find_recs(ailment, addr, ssn, d_str, t_str):
  if curr_id != -1:
    h_addr_cursor = g.conn.execute(text("SELECT A.h_address FROM admin_manages A WHERE A.employee_id = :id"),
                                   {'id': curr_id})
    g.conn.commit()

    h_addrs = []
    for result in h_addr_cursor:
      h_addrs.append(result[0])

    addr = h_addrs[0]

  recs = []
  distance = {}
  recs_cursor = g.conn.execute(text("SELECT DISTINCT H.h_address, H.name FROM Hospital H WHERE 0 < ALL (SELECT Res.num_available FROM resource_belongs_to Res, Requires Req WHERE H.h_address = Res.h_address AND Req.condition_name = :ailment AND Res.name = Req.name) INTERSECT (SELECT DISTINCT H.h_address, H.name  FROM Hospital H, Doctor D, works_at W WHERE (D.specialization = (SELECT doctor_specialization FROM Ailment WHERE condition_name = :ailment)) AND D.is_available = 't' AND H.h_address = W.h_address AND D.employee_id = W.employee_id)"),
                                   {'ailment': ailment})
  g.conn.commit()

  for result in recs_cursor:
    recs.append([result[0], result[1]])
    distance[(result[0], result[1], round(get_distance(result[0], addr), 2))] = round(get_distance(result[0], addr), 2)

  sorted_recs = list(dict(sorted(distance.items(), key=lambda item: item[1])).keys())
  if(len(sorted_recs)) > 3:
    sorted_recs = sorted_recs[:3]

  rec_addr = addr
  if curr_id == -1:
      rec_addr = 'None'

  for rec in sorted_recs:
    g.conn.execute(text("INSERT INTO refers(ssn, date, time, r_address, h_address, distance) VALUES(:ssn, :d_str, :t_str, :r_addr, :h_addr, :distance)"),{'ssn': ssn, 'd_str': d_str, 't_str': t_str, 'r_addr': rec[0], 'h_addr': rec_addr, 'distance': rec[2] })
    g.conn.commit()

  return sorted_recs

def input_patient(fname, lname, age, ssn, addr, ailment, d_str, t_str):

  full_name = fname+' '+lname

  p_addr = addr
  if curr_id == -1:
    h_addr = 'None'
  else:
    h_addr_cursor = g.conn.execute(text("SELECT A.h_address FROM admin_manages A WHERE A.employee_id = :id"),
                                   {'id': curr_id})
    g.conn.commit()

    h_addrs = []
    for result in h_addr_cursor:
      h_addrs.append(result[0])

    h_addr = h_addrs[0]

  g.conn.execute(text("INSERT INTO Patient_Goes_To (ssn, date, time, name, p_address, age, h_address)VALUES(:ssn, :d_str, :t_str, :name, :p_addr, :age, :h_addr)"),
                 {'ssn': ssn, 'd_str': d_str, 't_str': t_str, 'name': full_name, 'p_addr': p_addr, 'age': age, 'h_addr': h_addr})

  g.conn.execute(text("INSERT INTO Suffers_From (ssn, date, time, condition_name) VALUES(:ssn, :d_str, :t_str, :ailment);"),
                 {'ssn': ssn, 'd_str': d_str, 't_str': t_str, 'ailment': ailment})

  g.conn.commit()

  return 0

@app.route('/rec_submit', methods=['POST'])
def rec_submit():
  fname = request.form['fname']
  lname = request.form['lname']
  age = request.form['age']
  ssn = request.form['ssn']
  #if patient, use patient addr if not use h_addr
  addr = request.form['addr']
  ailment = request.form['ailment']

  now = datetime.now()
  t_str = now.strftime("%H:%M:%S")
  d_str = now.strftime("%Y-%m-%d")

  input_patient(fname, lname, age, ssn, addr, ailment, d_str, t_str)

  recs = find_recs(ailment, addr, ssn, d_str, t_str)
  rec_h_addrs = []

  for recc in recs:
    rec_h_addrs.append(recc[0])
  if len(recs) == 0:
    str = "There are no available hospitals that can treat you at this time."
  elif curr_id != -1:
    h_addr_cursor = g.conn.execute(text("SELECT A.h_address FROM admin_manages A WHERE A.employee_id = :id"),
                                   {'id': curr_id})
    g.conn.commit()

    h_addrs = []
    for result in h_addr_cursor:
      h_addrs.append(result[0])

    h_addr = h_addrs[0]
    if h_addr in rec_h_addrs:
      str = "Patient can be treated at the current hospital!"
      has_rec = False
      recs = []
  else:
    str = "These are the nearest hospitals:"
    has_rec = False
    if len(recs) > 0:
      has_rec = True

  return rec(str, has_rec, recs)

@app.route('/addemp', methods=['POST'])
def addemp(str = ''):
  context = dict(str=str)
  return render_template("addemp.html", **context)

@app.route('/addemp_submit', methods=['POST'])
def addemp_submit():
  fname = request.form['fname']
  lname = request.form['lname']
  full_name = fname+' '+lname
  doctor = request.form['doc']
  isDoctor = True
  spec = ''
  if doctor == 'T':
    isDoctor = True
    spec = request.form['spec']
  elif doctor == 'F':
    isDoctor = False

  admin = request.form['admin']
  isAdmin = True
  if admin == 'T':
    isAdmin = True
  elif doctor == 'F':
    isAdmin = False

  global max_emp
  max_emp = max_emp + 1
  g.conn.execute(text("INSERT INTO Employee (employee_ID, name) VALUES (:eID, :name)"),
                 {'eID': max_emp, 'name': full_name})
  g.conn.commit()

  #find curr address
  global curr_id

  h_addr_cursor = g.conn.execute(text("SELECT A.h_address FROM admin_manages A WHERE A.employee_id = :id"),
                                 {'id': curr_id})
  g.conn.commit()

  h_addr = []
  for result in h_addr_cursor:
    h_addr.append(result[0])

  if isDoctor:
    g.conn.execute(text("INSERT INTO Doctor (employee_ID, specialization, is_available) VALUES (:eID, :spec, :is_avail)"), {'eID': max_emp, 'spec': spec, 'is_avail': True})
    g.conn.execute(
      text(
        "INSERT INTO works_at (employee_ID, h_address) VALUES (:eID, :h_addr)"),
      {'eID': max_emp, 'h_addr': h_addr[0]})
    g.conn.commit()

  if isAdmin:

    uname = fname+'.'+lname
    pword = str.lower(lname)+'123!'
    g.conn.execute(
      text("INSERT INTO Admin_manages (employee_ID, username, password, h_address) VALUES (:eID, :uname, :pword, :h_addr)"), {'eID': max_emp, 'uname': uname, 'pword': pword, 'h_addr': h_addr[0]})
    g.conn.execute(
      text(
        "INSERT INTO employs (employee_ID, h_address) VALUES (:eID, :h_addr)"),
      {'eID': max_emp, 'h_addr': h_addr[0]})
    g.conn.commit()

  return another()


@app.route('/delemp', methods=['POST'])
def delemp(str=''):
  context = dict(str=str)
  return render_template("delemp.html", **context)

@app.route('/delemp_submit', methods=['POST'])
def delemp_submit():
  id = int(request.form['id'])

  #get curr address
  global curr_id

  h_addr_cursor = g.conn.execute(text("SELECT A.h_address FROM admin_manages A WHERE A.employee_id = :id"),
                                 {'id': curr_id})
  g.conn.commit()

  h_addr = []
  for result in h_addr_cursor:
    h_addr.append(result[0])

  #get list of all valid ids that curr user can delete
  id_cursor = g.conn.execute(text("(SELECT employee_id from employee EXCEPT (SELECT A.employee_id FROM admin_manages A FULL OUTER JOIN doctor D ON A.employee_id=D.employee_id)) UNION (SELECT A.employee_id FROM admin_manages A FULL OUTER JOIN works_at W ON A.employee_id = W.employee_id WHERE (A.h_address = :h_addr OR W.h_address = :h_addr))"), {'h_addr': h_addr[0]})

  valid_ids = []
  for result in id_cursor:
    valid_ids.append(result[0])



  if id in valid_ids:
    g.conn.execute(text("DELETE FROM works_at WHERE Employee_ID = :eID"), {'eID': id})
    g.conn.execute(text("DELETE FROM employs WHERE Employee_ID = :eID"), {'eID': id})
    g.conn.execute(text("DELETE FROM Employee WHERE Employee_ID = :eID"), {'eID': id})
    g.conn.commit()

    return another()

  else:
    str = "Either this id does not exist or you do not have permission to delete employee with id %s" % id
    return delemp(str)


@app.route('/viewres', methods=['POST'])
def viewres(str=''):
  context = dict(str=str)
  return render_template("viewres.html", **context)


@app.route('/viewres_submit', methods=['POST'])
def viewres_submit():
  h_addr = request.form['hospital']
  res = request.form['res']

  name_cursor = g.conn.execute(
    text("Select name from hospital where h_address = :h_addr"), {'h_addr': h_addr})
  g.conn.commit()

  names = []
  for result in name_cursor:
    names.append(result[0])

  #get this from query
  count_cursor = g.conn.execute(text("Select num_available from resource_belongs_to where h_address = :h_addr and name = :res"), {'h_addr': h_addr, 'res': res})
  g.conn.commit()

  counts = []
  for result in count_cursor:
    counts.append(result[0])

  if len(counts) == 0:
    str = f"The the resource '{res}' is not available at {names[0]}"
  else:
    count = counts[0]
    str = f"There are {count} of the resource '{res}' at {names[0]}."

  return viewres(str)

@app.route('/changeres', methods=['POST'])
def changeres(str=''):
  context = dict(str=str)
  return render_template("changeres.html", **context)

@app.route('/changeres_submit', methods=['POST'])
def changeres_submit():
  res = request.form['res']
  num = int(request.form['num'])


 # cursor.execute("""SELECT admin FROM users WHERE username = %(username)s""", {'username': username})

  ##DO THIS FOR INJECTIONS
  #str = f"SELECT A.h_address FROM admin_manages A WHERE A.h_address = %s" % bruh
  global curr_id

  h_addr_cursor = g.conn.execute(text("SELECT A.h_address FROM admin_manages A WHERE A.employee_id = :id"), {'id': curr_id})
  g.conn.commit()

  h_addr = []
  for result in h_addr_cursor:
    h_addr.append(result[0])

  if len(h_addr) == 1:
    total_num_cursor = g.conn.execute(text("SELECT R.num_total FROM resource_belongs_to R WHERE R.name = :name AND R.h_address = :h_addr"), {'name': res, 'h_addr': h_addr[0]})
    g.conn.commit()

  total_nums = []
  for result in total_num_cursor:
    total_nums.append(result[0])

  if len(total_nums) == 1:
    total_num = total_nums[0]
  else:
    str = f"Your hospital does not have '{res}' as a possible resource."
    return changeres(str)


  if total_num < num:
    str = f"The number you inputted is greater than the total number of the resource '{res}' at your hospital. Please enter a number less than {total_num}."
    return changeres(str)
  else:
    percent_available = round(float(num)/float(total_num), 2)
    g.conn.execute(text("UPDATE resource_belongs_to SET num_available = :num, percent_available = :pavail WHERE name = :name AND h_address = :h_addr"),
                   {'num': num, 'pavail': percent_available, 'name': res, 'h_addr': h_addr[0]})
    g.conn.commit()
    return another()

#Login Pressed
@app.route('/login', methods=['POST'])
def login():
  uname = request.form['uname']
  pword = request.form['pword']

  #g.conn.execute(text('INSERT INTO test(name) VALUES (:name)'), params_dict)
  cursor = g.conn.execute(text(f'SELECT E.employee_id, E.name  FROM admin_manages A, employee E WHERE E.employee_id = A.employee_id AND (A.username = \'{uname}\' AND A.password = \'{pword}\')'))
  g.conn.commit()

  ids = []
  names = []
  for result in cursor:
    ids.append(result[0])
    names.append(result[1])

  if len(ids) == 1:
    global curr_id
    curr_id = int(ids[0])
    return another()
  else:
    str = 'Either username or password is incorrect'
    return index(str)


@app.route('/logout', methods=['POST'])
def logout():
  global curr_id
  curr_id = -1
  return redirect('/')


if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using:

        python3 server.py

    Show the help text using:

        python3 server.py --help

    """

    HOST, PORT = host, port
    print("running on %s:%d" % (HOST, PORT))
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

  run()

