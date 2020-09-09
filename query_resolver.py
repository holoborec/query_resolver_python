#!/usr/bin/python3

#XQR:xholec07

import sys, xml.etree.ElementTree as ET, os

#Funkcia vytlaci napovedu na standardny vystup.
def print_help():
  print("Skript prevadza zadany select dotaz nad zadanym suborom vo formate XML.\n"
        "Za implicitny vstupny resp. vystupny subor sa povazuje stdin resp. stdout.\n"
        "--inputfile a --outputfile explicitne specifikuju vstupny resp. vystupnu subor.\n"
        "Prikaz select bude zadany jednou z dvoch moznosti: \n"
        "1) priamo v argumente --query\n"
        "2) v subore specifikovanom --qf\n"
        "argument -n nebude generovat XML hlavicku na vystupe\n"
        "--root=element - element bude korenovy element obalujuci vysledky.\n"
        "Argumenty --query a --qf nie je mozne navajom kombinovat.\n"       
        )
  sys.exit(0)  

#Funckia parsuje argumenty, uklada si potrebne informacie pre dalsi
#beh programu a v pripade chyb konci beh skriptu s chybou c. 1
def get_args():
  args = dict();  #slovnik (key -> value) s hodnotami argumentov
  sys_args = sys.argv #sys_args[0] bude meno skriptu
  
  if '--help' in sys_args:
    if len(sys_args) == 2:
      print_help()
    else:
      sys.stderr.write("Parameter --help nie je mozne kombinovat so ziadnym dalsim.")
      sys.exit(1)
  #Vzdy kontrolujeme duplicitu daneho argumentu
  for arg in sys_args[1:]: #prechadzame vsetky argumenty okrem mena skriptu
    if arg.startswith('--input='): 
      if 'inputFile' in args:
        sys.stderr.write("Parameter --input bol zadany viackrat.\n")
        sys.exit(1)
      else:
        args['inputFile'] = arg[8:]
    elif arg.startswith('--output='):
      if 'outputFile' in args:
        sys.stderr.write("Parameter --output bol zadany viackrat.\n")
        sys.exit(1)
      else:
        args['outputFile'] = arg[9:]
    elif arg.startswith('--query'):
      if 'query' in args:
        sys.stderr.write("Parameter --query bol zadany viackrat.\n")
        sys.exit(1)
      else:
        args['query'] = arg[8:]
    elif arg.startswith('--qf'):
      if 'qf' in args:
        sys.stderr.write("Parameter --qf bol zadany viackrat.\n")
        sys.exit(1)
      else:
        args['qf'] = arg[5:]
    elif arg.startswith('-n'):
      if 'n' in args:
        sys.stderr.write("Parameter -n bol zadany viackrat.\n")
        sys.exit(1)
      else:
        args['n'] = True;
    elif arg.startswith('--root='):
      if 'rootElement' in args:
        sys.stderr.write("Parameter --root bol zadany viackrat.\n")
        sys.exit(1)   
      else:
        args['rootElement'] = arg[7:]
    else:
      sys.stderr.write("Bol zadany neznamy parameter.\n")
      sys.exit(1)
  ##musi byt zadany presne jeden z dvojice parametrov query a qf
  if (('query' in args and 'qf' in args) or ('query' not in args and 'qf' not in args)):
    sys.stderr.write("Nespravna kombinacia parametrov query a qf - zadane oba alebo ani jeden.\n")
    sys.exit(1) 
  
  return args

#V tejto funkcii prebieha rozdelenie vstupneho prikazu SELECT 
#na mensie casti. Vystupom je viac premennych s obsahom elementov a inych 
#premennych, ktore ovplyvnia nasledny vyber z XML dokumentu  
def query_clauses(query_content):
  query_words = query_content.split() #Rozdelime na slova
  clauses = ['SELECT','LIMIT','FROM','WHERE','ORDER']  #klucove slova klauzuli
  limit = -1
  from_clause = ''
  where_element = ''
  negation = False
  relation_operator = ''
  literal = ''
  order_element = ''
  ordering = ''
  string = False
  
  #Postupna kontrola potrebnych klauzuli a ukladanie si obsahu
  if bool(query_words) == False:  #prazdny prikaz select
     sys.stderr.write("Zadany dotaz je prazdny.\n")
     sys.exit(80)
  #prve slovo dotazu musi byt SELECT
  if query_words[0] != 'SELECT':
    sys.stderr.write("Zadany dotaz neobsahuju klauzulu SELECT.\n")
    sys.exit(80)
  #Klauzula FROM je povinna
  if 'FROM' not in query_words:
    sys.stderr.write("Zadany dotaz neobsahuje klauzulu FROM.\n")
    sys.exit(80)
  #druhe slovo je automaticky element, ktory ma byt selektovany
  if len(query_words) > 1:
    if query_words[1] not in clauses: 
      selected_element = query_words[1]
  else:
    sys.stderr.write("Neobsahuje element na vybratie prikazom SELECT.\n")
    sys.exit(80)
    
  #Cyklus osetrujuci zvysny obsah dotazu
  index = 2  #zacneme za klauzulou "SELECT element"
  clauses.remove('SELECT') #Select sa uz nemoze vyskytnut znova
  while index < len(query_words):
    if query_words[index] in clauses: #Hladame klucove slova klauzuli
      #LIMIT CLAUSE
      if query_words[index] == 'LIMIT':
        clauses.remove('LIMIT') #aby sa nevyskytlo druhykrat
        if query_words[index+1].isdigit(): #limit musi byt nutne cislo
          limit = query_words[index+1]
          limit = int(limit)
          index = index + 1
        else:
          sys.stderr.write("Po klauzuli LIMIT nenasleduje cislo.\n")
          sys.exit(80)
      #FROM CLAUSE
      if query_words[index] == 'FROM':
        if 'LIMIT' in clauses: #ak sa klauzula LIMIT nevyskytla doteraz, uz sa nemoze
          clauses.remove('LIMIT') 
        clauses.remove('FROM') #opatovny vyskyt from bude viest na chybu
        if index + 1 < len(query_words) and query_words[index] not in clauses: #from ma volitelnu cast
          index = index + 1
          from_clause = query_words[index]
        
      #WHERE CLAUSE
      if query_words[index] == 'WHERE':
        clauses.remove('WHERE')
        index = index + 1
        index_not = index
        negation = False
        #klauzula WHERE obsahuje CONDITION
        #Condition sa sklada z troch prvkov
        #element, operator, literal
        if index + 3 > len(query_words):
          sys.stderr.write("Nespravna konstrukcia klauzule WHERE.\n")
          sys.exit(80)
        #Novym ukazovatkom prebehneme zvysok prikazu SELECT a hladame vyskyty NOT
        #Vzdy pri dalsom vyskyte NOT preklapame hodnotu z T na F alebo naopak
        #Posuvame hlavne ukazovatko INDEX v pripade ze sme narazili na NOT
        while index_not < len(query_words):
          if query_words[index_not] == 'NOT':
            if negation == False:
              negation = True
            else:
              negation = False
            index_not = index_not + 1
            index = index + 1 #poskakujeme dalej za vsetky NOT-y
          else: 
            index_not = index_not + 1
        #spracujeme element, prva cast condition vyrazu    
        if index >= len(query_words):
          sys.stderr.write("V klauzuli WHERE chyba cely vyraz.\n")
          sys.exit(80)
        where_element = query_words[index]
        
        #konrola validity where_elementu
        where_check = where_element.split('.')
        if where_check[0].isalpha() != True:  #element musi byt prazdny alebo znakovy
          if where_check[0] != "":
            sys.stderr.write("Where element obsahuje nepovolene znaky.\n")
            sys.exit(80)
        if len(where_check) > 1: #atribut nie je zadany alebo je znakovy
          if where_check[1].isalpha() != True:
            sys.stderr.write("Where element obsahuje nepovolene znaky.\n")
            sys.exit(80)
        if len(where_check) > 2: #viac ako jedna bodka sa vo vyraze nachadzat nesmie
          sys.stderr.write("Where element obsahuje nepovolene znaky.\n")
          sys.exit(80)  
          
        
        index = index + 1
        if index >= len(query_words):
          sys.stderr.write("V klauzuli WHERE chyba operator.\n")
          sys.exit(80)
        relation_operator = query_words[index] #nacitame znak porovnania
        
        #kontrola validity relacneho operatoru:
        if relation_operator != "=" and relation_operator != "<" and relation_operator != ">" and relation_operator != "CONTAINS":
          sys.stderr.write("Relacny operator nie je validny.\n")
          sys.exit(80)
 
        #Nacitame tretiu cast podmienky - literal
        index = index + 1
        if index >= len(query_words):
          sys.stderr.write("V klauzuli WHERE chyba literal.\n")
          sys.exit(80)
        literal = query_words[index]
        
      #ORDERBY CLAUSE
      if query_words[index] == 'ORDER':
        if 'WHERE' in clauses: #WHERE uz sa po ORDER nemoze vyskytnut
          clauses.remove('WHERE')
        clauses.remove('ORDER') #ORDER druhykrat tiez nebudeme akceptovat
        #po ORDER musi nutne nasledovat klucove slovo BY
        index = index + 1
        if index >= len(query_words):
          sys.stderr.write("V klauzuli ORDERBY chyba klucove slovo BY.\n")
          sys.exit(80)
        if query_words[index] != 'BY': 
          sys.stderr.write("V klauzuli ORDERBY chyba klucove slovo BY.\n")
          sys.exit(80)
        #povinny je taktiez radiaci element  
        index = index + 1
        if index >= len(query_words):
          sys.stderr.write("V klauzuli ORDERBY chyba radiaci element.\n")
          sys.exit(80)  
        order_element = query_words[index]
        #a netreba zabudnut na sposob radenia
        index = index + 1
        if index >= len(query_words):
          sys.stderr.write("V klauzuli ORDERBY chyba sposob zoradovania.\n")
          sys.exit(80)
        ordering = query_words[index]
        if order_element == "" or ordering == "":
          sys.stderr.write("V klauzuli ORDER BY nie je specifikovany radiaci element alebo sposob radenia.\n")
          sys.exit(80)
        
        #kontrola validity zoradovania - povolene hodnoty su ASC a DESC
        if ordering != "ASC" or ordering != "DESC":
          sys.stderr.write("Neznamy sposob radenia - povolene je len ASC a DESC.\n")
          sys.exit(80)  
    
    else: #nenarazili sme na klucove slovo, jedna sa o chybu, nezname slovo v dotaze
      sys.stderr.write("Zadany vyraz WHERE nesplna pozadovany format.\n")
      sys.exit(80)
    index = index + 1 #posun na dalsie slovo
    
  #pokial bol zadany operator, odstranime pripadne prebytocne biele znaky  
  if relation_operator != '':
    relation_operator = relation_operator.strip()
  
  if literal != '': #pokial bol zadany literal, treba rozlisit, ci sa jedna o string alebo number
    if '"' in literal: #pravdepodobne ide o string
      if literal.startswith('\"') and literal.endswith('\"'): #string zacina a konci znakom "
        literal = literal.replace("\"", "")
        string = True;
      else:  #string nesmie obsahovat 1 alebo 3 a viac uvodzoviek
        sys.stderr.write("Nespravny pocet uvodzoviek v porovnavacom stringu.\n")
        sys.exit(80)  
    else: #bude sa jednat o numericku hodnotu
      if literal.isnumeric():
        literal = int(literal)
      else: #ani string, ani number => chyba
        sys.stderr.write("Zadany literal nie je ani string, ani number.\n")
        sys.exit(80)  
  #Nie je testovat, ci dany element obsahuje number, iba string
  if string == False and relation_operator == "CONTAINS": 
    sys.stderr.write("Nie je mozne previest operator contains nad nestringovym retazcom.\n")
    sys.exit(80)  
  #vsetky ziskane informacie propagujeme do funkcie main
  return selected_element, limit, from_clause, negation, where_element, relation_operator, literal, string, order_element, ordering

#Funkcia find reaguje na obsah klauzule FROM
#Ako vstup prijima cely XML strom a element pripadne atribut
#ktory bude mat ostat vo vystupe (konkretne jeho prvy vyskyt)  
def find(tree, from_element, from_attribute):
  #ak bola klauzula from prazdna, nevyberame nic
  if not from_element and not from_attribute:
    return None
  #root reprezentuje "vsetko"  
  if from_element == "ROOT":
    from_element = None
  #iterujeme nad celym stromom kde sa nachadza element  
  for i in tree.iter(from_element):
    if not from_attribute: #ak nie je specifikovany atribut, vraciame vsetky vyskyty
      return i
    elif from_attribute in i.attrib: #ak bol specifikovany atribut, musime pozerat aj nan
      return i
  return None


#Funkcia, ktora sa stara o splnenie podmienky v klauzuli WHERE
#Ako vstup prijima XML strom splunujuci podmienku FROM a premenne reprezentujuce podmienku
#Vystupom je XML strom zredukovany na strom splnajuci podmienku 
def where_statement(found, select_element, negation, where_element, where_attribute, relation_operator, literal, string):
  newfound = list() 
  #V pripade negacie zamiename vyznam matematickych operacii
  if negation == True:
    if relation_operator == "=":
      relation_operator = "!="
    elif relation_operator == ">":
      relation_operator = "<"
    elif relation_operator == "<":
      relation_operator = ">"
  #Prechod vsetkymi elementami povodneho stromu s vyskytom elementu urceneho podmienkou
  for i in found.iter(select_element):
    for j in i.iter(where_element):
      #zohladnujeme pripadny obsah atributu
      if where_attribute: 
        statement = j.attrib.get(where_attribute)
      else:
        if list(j) and where_element: #pokial obsahuje vnorene elementy
          sys.stderr.write("Element nie je koncovy element.\n")
          sys.exit(4)
        statement = j.text
      if string == False: #ak sa jedna o numericke cislo a porovnavat budeme matematicky, nie lexikograifcky
        try:
          statement = float(statement)
        except: 
          continue
      #Vzdy pridame do vystpneho zoznamu len prvky splnajuce podmienku    
      if relation_operator == "CONTAINS" and negation == False:
        if statement and literal in statement: 
          newfound.append(i)
      #negovane contains znamena "neobsahuje"    
      elif relation_operator == "CONTAINS" and negation == True:
        if statement and literal not in statement: 
          newfound.append(i)
      elif relation_operator == "=":
        if statement == literal:
          newfound.append(i)
      elif relation_operator == "<":
        if statement < literal:
          newfound.append(i)
      elif relation_operator == ">":
        if statement > literal:
          newfound.append(i)
      elif relation_operator == "!=":
        if statement != literal:
          newfound.append(i)
  
  return newfound 
    

def main():
  #slovnik argumentov  
  args = get_args()
  
  #otvorenie vstupneho suboru na citanie
  if 'inputFile' in args: 
    try:
      in_stream = open(args['inputFile'] , 'r')   
    except: 
      sys.stderr.write("Zadany vstupny subor nejde otvorit.\n")
      sys.exit(2)
  else: #ak nebol zadany argumentom, implicitne bude standardny vstup
    in_stream = sys.stdin
  
  #otvorenie vystupneho suboru na zapis    
  if 'outputFile' in args: 
    try:
      out_stream = open(args['outputFile'] , 'w')   
    except: 
      sys.stderr.write("Zadany vystupny subor nejde otvorit.\n")
      sys.exit(3)
  else: #ak nebol zadany argumentom, implicitne bude standardny vystup
    out_stream = sys.stdout
  
  #ak bude dotaz v specialnom subore, otvorime ho  
  if 'qf' in args:
   try:
     query_file = open(args['qf'], "r")
     query_content = query_file.read()
   except:
     sys.stderr.write("Zadany subor query s dotazom nejde otvorit.\n")
     sys.exit(2)  
  #ak bol dotaz zadany priamo v prikazovom riadku v parametre query
  if 'query' in args:
    query_content = args['query']
  
  #Rozdelenie dotazu na klauzule a mensie casti
  select_element, limit, from_clause, negation, where_clause, relation_operator, literal, string, order_element, ordering = query_clauses(query_content)
  
  #Prevod vstupneho XML suboru na XML strom
  try:
    tree = ET.parse(in_stream)
  except: 
    sys.stderr.write("Zadany XML subor nema spravny format.\n")
    sys.exit(4)
  
  #test, ci sa jedna o element, element.attr alebo .attr  
  from_clause = from_clause.split('.')
  if from_clause[0]:
    from_element = from_clause[0]
  else:
    from_element = None
  if len(from_clause) > 1:
    from_attribute = from_clause[1]
  else:
    from_attribute = None
  if len(from_clause) > 2:
    sys.stderr.write("From klauzula obsahuje element v nespravnom formate.\n")
    sys.exit(80)
    
  #Vstup zredukujeme na elementy splnajuce klauzulu FROM
  found = find(tree, from_element, from_attribute)
  
  #test, ci sa jedna o element, element.attr alebo .attr
  where_clause = where_clause.split('.')
  where_element = where_clause[0]
  if len(where_clause) > 1:
    where_attribute = where_clause[1]
  else:
    where_attribute = ''
  
  if found is None: #ak mame po from prazdny zoznam, netreba volat where_statement
    newfound = None
  elif relation_operator: #ak mame relacny operator (teda aj celu podmienku WHERE), volame funkciu where_statement
    #Dostavame xml strom zredukovany na elementy splnajuce WHERE podmienku
    newfound = where_statement(found, select_element, negation, where_element, where_attribute, relation_operator, literal, string)
  else: #Found je neprazdne, ale WHERE klauzula nebola zadana:
    #skopirujeme jedna k jednej povodny XML strom na zaklade toho, co chceme SELECTNUT, bez dalsej obmedzujucej podmienky
    newfound = [x for x in found.iter(select_element)]
    
  #Kym uzivatel nezakazal, budeme tlacit xml hlavicku
  if 'n' not in args:
    out_stream.write('<?xml version="1.0" encoding="utf-8"?>')
  if newfound: #pokial nieco vyhovelo SELECT dotazu
    if 'rootElement' in args: #pociatocny tag s root elementom
      out_stream.write("<" + args['rootElement'] + ">")
    if int(limit) != -1: #pokial bol uzivatelom zadany LIMIT
      for tag in newfound[:limit]: #zobrazi sa len prvych LIMIT vyskytov
        out_stream.write(ET.tostring(tag, encoding = "unicode"))
    else:
      for tag in newfound: #limit zadany nebol, tlacime vsetko
        out_stream.write(ET.tostring(tag, encoding = "unicode"))
    if 'rootElement' in args: #koncovy tag s root elementom
      out_stream.write("</" + args['rootElement'] + ">")
  else: #ziadne elementy nevyhoveli filtru v podobe dotazu
    if 'rootElement' in args:
      out_stream.write("<" + args['rootElement'] + "/>") #jeden tag reprezentujuci sucasne pociatocny aj koncovy XML tag 
     
  out_stream.write("\n")  
       
if __name__ == "__main__":
    main()


    
    
     
   
  
  