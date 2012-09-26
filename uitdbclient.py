#!/usr/bin/python -tt
# -*- coding: UTF-8 -*-

import argparse, sys, httplib, urllib, urllib2
import xml.dom.minidom
import time, datetime
import os
from xml.dom.minidom import Document
from xml.sax.handler import ContentHandler

# argparser:
parser = argparse.ArgumentParser()
parser.add_argument("-f", "--file", help="upload CdbXML doc from your filesystem")
parser.add_argument("-id", "--cdbid", help="ID of object to perform operation on")
parser.add_argument("-v", "--verbosity", help="print parser outcome to screen", action="store_true")
parser.add_argument("-s", "--save_report", help="save parser outcome to file", action="store_true")
parser.add_argument("-d", "--delete", help="delete item, use with --cdbid", action="store_true")
parser.add_argument("-k", "--keywords", help="add keywords, use with --cdbid")
parser.add_argument("-o", "--obj_type", help="choose: event, actor, production")
parser.add_argument("-l", "--lang", help="translation: to nl, fr, en, use with --cdbid")
parser.add_argument("-td", "--title", help="title translation, use with --lang")
parser.add_argument("-sd", "--shortdescription", help="short description translation, use with --lang")
parser.add_argument("-ld", "--longdescription", help="long description translation, use with --lang")

if len(sys.argv)==1:
  parser.print_help()
  sys.exit(1)

args = parser.parse_args()

def fileupload(filename):
  print "START PROCESSING"

  try:
    doc = xml.dom.minidom.parse(filename)
    _process_content_objects(doc)
  except Exception, e:
    print "Error occured while parsing XML: %s" % e
    sys.exit(1)

  print "PROCESSING FINISHED"

def addkeywords(cdbid, keywords):
  objecttype = _find_object_type(cdbid)
  path = "/api/v1/" + objecttype + "/" + cdbid + "/keywords"
  formfields = {'keywords': keywords}
  headers = {"Content-Length" : len(keywords)}
  httpmethod = "POST"
  _modify_content_object(path, headers, formfields, httpmethod)
      
def addtranslation(cdbid, lang, formfields):
  objecttype = _find_object_type(cdbid)
  
  if lang:
    formfields['lang'] = lang
  else:
    print "lang is required"
    sys.exit(1)
  
  path = "/api/v1/" + objecttype + "/" + cdbid + "/translations"
  headers = {"Content-Length" : len(formfields)}
  httpmethod = "POST"
  _modify_content_object(path, headers, formfields, httpmethod)
      
def deleteitem(cdbid):
  objecttype = _find_object_type(cdbid)
  path = "/api/v1/" + objecttype + "/" + cdbid
  formfields = {}
  headers = {"Content-Length" : len(cdbid)}
  httpmethod = "DELETE"
  _modify_content_object(path, headers, formfields, httpmethod)

def _find_object_type(cdbid):
  if args.obj_type:
    return args.obj_type
    
  objecttypes = ['event', 'actor', 'production']
  
  for objecttype in objecttypes:
    r1 = _connect_to_uitdb()
    userkey = _get_userkey(r1.read())
    url = "http://test.rest.uitdatabank.be/api/v1/" + objecttype + "?q=" + cdbid + "&key=" + userkey
    r2 = urllib2.urlopen(url)
    doc = xml.dom.minidom.parse(r2)
    nofrecords = doc.getElementsByTagName("nofrecords")
    found = nofrecords[0].firstChild.nodeValue  
  
    if found:
      rvalue = objecttype
      break
  
  return rvalue

def _modify_content_object(path, headers, formfields, httpmethod):
  # connect to uitdb
  response = _connect_to_uitdb()
  # authenticate user
  userkey = _get_userkey(response.read())

  if response.getcode() == 200 and userkey:
    formfields['key'] = userkey
    params = urllib.urlencode(formfields)
    path = path + "?" + params
    print path
    conn = httplib.HTTPConnection("test.rest.uitdatabank.be")
    conn.request(httpmethod, path, "", headers) 
    starttime = time.time()
    response = conn.getresponse()
    endtime = time.time()
    duration = round((endtime - starttime) * 1000)
    data = response.read()
    conn.close()
    
    # Print the response analyses
    result = {}
    result['http_response'] = str(response.status) + ' ' + str(response.reason)
    result['duration_ms'] = str(duration)
    result['api_response'] = data 
    
    if args.verbosity:
      for key, value in result.items():
        print key, ':', str(value)
      print '-----------------------'
  else:
    print "HTTP connection closed with error status: %s" % r1.status
    sys.exit(1)

def _process_content_objects(doc):
  cnt = 0
  results = []

  # connect to uitdb
  response = _connect_to_uitdb()
  #authenticate user
  userkey = _get_userkey(response.read())
    
  if response.getcode() == 200 and userkey:
    # Parse the input XML document
    try:
      if doc.getElementsByTagName("events"):
        item_type = 'event'
      elif doc.getElementsByTagName("actors"):
        item_type = 'actor'
      elif doc.getElementsByTagName("productions"):
        item_type = 'production'
      
      content_objects = doc.getElementsByTagName(item_type)

      for co in content_objects:
        # Number of event in input XML 
        cnt += 1
        
        # Create the output XML document
        doc = Document()
        cdbxml = doc.createElement("cdbxml")
        cdbxml.setAttribute("xmlns", "http://www.cultuurdatabank.com/XMLSchema/CdbXSD/3.1/FINAL")
        doc.appendChild(cdbxml)
        list_element = doc.createElement(item_type + 's')
        cdbxml.appendChild(list_element)
        list_element.appendChild(co)
        xml_output = doc.toxml().encode('utf-8')
      
        # Send the XML to the Entry API and measure duration
        params = urllib.urlencode({'key': userkey})
        headers = {"Content-type": "text/xml", "Content-Length" : len(xml_output)}

        conn = httplib.HTTPConnection("test.rest.uitdatabank.be")
        conn.request("POST", "/api/v1/" + item_type + "?" + params, "",headers)
        conn.send(xml_output)
        starttime = time.time()
        r2 = conn.getresponse()
        endtime = time.time()

        duration = round((endtime - starttime) * 1000)
        data = r2.read()
        conn.close()
        
        # Print the response analyses
        result = {}
        result['item_nr'] = str(cnt)
        result['item_type'] = item_type
        result['item_externalid'] = co.getAttribute('externalid')
        result['http_response'] = str(r2.status) + ' ' + str(r2.reason)
        result['duration_ms'] = str(duration)
        result['api_response'] = data 
        
        if args.verbosity:
          for key, value in result.items():
            print key, ':', str(value)
          print '-----------------------'
        
        results.append(result)
        
    except Exception, e:
      print "Error occured while parsing XML: %s" % e
      sys.exit(1)

    # Create report in current working directory
    if args.save_report:
      try:
        doc = Document()
        report = doc.createElement("report")
        doc.appendChild(report)
        for result in results:
          item = doc.createElement("item")
          item.setAttribute('type', result['item_type'])            
          item.setAttribute('nr', result['item_nr'])
          item.setAttribute('external_id', result['item_externalid'])
          item.setAttribute('http_response', result['http_response'])
          item.setAttribute('duration_ms', result['duration_ms'])
          report.appendChild(item)
        xml_output = doc.toxml().encode('utf-8')
        path = os.getcwd() + '/report_' + datetime.datetime.now().strftime("%Y%m%d%H%M") + '.xml'
        file = open(path, 'w')
        file.write(xml_output)
        file.close()
        print "File created: '%s'" % path 
      except Exception, e:
        print "Creating document closed with error: %s" % e
  else:
    print "HTTP connection closed with error status: %s" % r1.status
    sys.exit(1)
    
def _get_userkey(api_response):
  doc = xml.dom.minidom.parseString(api_response)
  key = doc.getElementsByTagName("message")
  return " ".join(t.nodeValue for t in key[0].childNodes if t.nodeType == t.TEXT_NODE)

def _connect_to_uitdb():
  try:
    response = urllib2.urlopen("http://test.rest.uitdatabank.be/api/v1/token")
  except urllib2.HTTPError, e:
    print "HTTP connection closed with error: %s" % e.read()
    sys.exit(1)
  return response

def main():
  if args.file:
    fileupload(args.file)

  if args.cdbid:
    if args.delete:
      deleteitem(args.cdbid)
    if args.keywords:
      addkeywords(args.cdbid, args.keywords)
    if args.lang:
      formfields = {}
      
      if args.title:
        formfields['title'] = args.title
      if args.shortdescription:
        formfields['shortdescription'] = args.shortdescription
      if args.longdescription:
        formfields['longdescription'] = args.longdescription
      addtranslation(args.cdbid, args.lang, formfields)

if __name__ == '__main__':
  main()
