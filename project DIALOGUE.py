# -*- coding: utf-8 -*-
# author: Superkebabbie
# version: 1.3 (packed and shipped)
# now independent of MCEdit and chunk loading

import sys, os, shutil
import re

import tkinter as tk
from tkinter import filedialog, messagebox

sys.modules['_elementtree'] = None
import xml.etree.ElementTree as xTree
#workaround enabling line numbers to be added to the eTree
#courtesy of Duncan Harris
class LineNumberingParser(xTree.XMLParser):
    def _start(self, *args, **kwargs):
        # Here we assume the default XML parser which is expat
        # and copy its element position attributes into output Elements
        element = super(self.__class__, self)._start(*args, **kwargs)
        element.sourceline = self.parser.CurrentLineNumber
        element.sourcecol = self.parser.CurrentColumnNumber
        return element

    def _end(self, *args, **kwargs):
        element = super(self.__class__, self)._end(*args, **kwargs)
        element.sourcelineend = self.parser.CurrentLineNumber
        element.sourcecolend = self.parser.CurrentColumnNumber
        return element
        
class SimpleTerminationException(Exception):
    def __init__(self, reason, exception=None):
        self.reason = reason
        
    def __str__(self):
        return 'APPLICATION TERMINATED: ' + self.reason

# -------------------- STYLE ---------------------#
        
class Style:    
    def __init__(self,str):
        #l=bold,o=italic,n=underline,m=strikethrough,k=obfuscated
        self.bold = True          if 'l' in str else False
        self.italic = True        if 'o' in str else False
        self.underlined = True    if 'n' in str else False
        self.strikethrough = True if 'm' in str else False
        self.obfuscated = True    if 'k' in str else False
    
    def toTellrawProperties(self):
        return "%s%s%s%s%s"%(',"bold":%s'%str(self.bold).lower(),
                             ',"italic":%s'%str(self.italic).lower(),
                             ',"underlined":%s'%str(self.underlined).lower(),
                             ',"strikethrough":%s'%str(self.strikethrough).lower(),
                             ',"obfuscated":%s'%str(self.obfuscated).lower())
    
    def copy(self):
        return Style('%s%s%s%s%s'%('l' if self.bold else '',
                                   'o' if self.italic else '',
                                   'n' if self.underlined else '',
                                   'm' if self.strikethrough else '',
                                   'k' if self.obfuscated else ''))

#---------------- ELEMENT HANDLERS ----------------#

def handleText(element,vars):
    #leaf function
    vars = readAttributes(element,vars,['delay','col','style','name','namecol','namestyle'])
    vars = doConvergence(vars)
    lines = [s for s in [l.lstrip('\t ') for l in element.text.split('\n')] if s != '']#string formatting: cut newlines and tabs and remove empty lines
    for l in lines:
        try:
            write(toMessage(l,vars,header='TEXT: %s'%l.upper()))
        except UnknownFormattingCodeError as e:
            raise UnknownFormattingCodeError("%s in 't' at line %d"%(str(e),element.sourceline))
        vars['tick'] += vars['delay']
    goDeeper(element,vars,[])#checks if leaf does not have children
    vars = makeEnd(vars)
    return vars
        
def handleCommand(element,vars):
    #leaf function
    vars = readAttributes(element,vars,['delay'])
    vars = doConvergence(vars)
    lines = [s for s in [l.lstrip('\t ') for l in element.text.split('\n')] if s != '']#string formatting: cut newlines and tabs and remove empty lines
    for l in lines:
        write(toCommand(vars['tick'],vars['seg'],l.lstrip('/'),header='COMMAND: %s'%l.upper()))
        vars['tick'] += vars['delay']
    goDeeper(element,vars,[])#checks if leaf does not have children
    vars = makeEnd(vars)
    return vars
    
def handlePause(element,vars):
    #leaf function
    vars = readAttributes(element,vars,[])#run to give users feedback if the use attibutes here (of which there are none supported here)
    vars = doConvergence(vars)
    vars['tick'] += int(element.text)
    goDeeper(element,vars,[])#checks if leaf does not have children
    vars = makeEnd(vars)
    return vars
    
def handleConcatText(element,vars):
    #leaf function, only to be used within a concat
    vars = readAttributes(element,vars,['col','style'])
    lines = [s for s in [l.lstrip('\t ') for l in element.text.split('\n')] if s != '']#string formatting: cut newlines and tabs and remove empty lines
    vars['name'] = '' #removes name compound from underlying text elements
    for l in lines:
        try:
            vars['compounds'].extend(constructCompounds(l,vars))
        except UnknownFormattingCodeError as e:
            raise UnknownFormattingCodeError("%s in 't' at line %d"%(str(e),element.sourceline))
    goDeeper(element,vars,[])#checks if leaf does not have children
    return vars
    
def handleConcat(element,vars):
    #semi-leaf, only accepts t
    #makes all t contained within a single line, allows for easy formatting
    global getHandleFunction
    vars = readAttributes(element,vars,['col','style','name','namecol','namestyle','sep'])
    vars = doConvergence(vars)
    getHandleFunction['t'] = handleConcatText #override handle function
    vars['compounds'] = []
    if vars['name'] != '': vars['compounds'].append(TextCompound('[%s] '%vars['name'],vars['namecol'],vars['namestyle']))
    vars = goDeeper(element,vars,['t'],upstream_vars=['maxSeg','ends','tick','compounds'])
    if 'sep' in vars:
        start = 1 if vars['name'] == '' else 2#no sep between name and first compound
        for idx in reversed(range(start,len(vars['compounds']))):
            vars['compounds'].insert(idx,TextCompound(vars['sep'],vars['textcol'],vars['style']))
    write(toCommand(vars['tick'],vars['seg'],'tellraw @a '+toTellraw(vars['compounds']),header='TEXT (COMP.): %s'%''.join([str(c).upper() for c in vars['compounds']])))
    getHandleFunction['t'] = handleText #reset handle function
    vars['tick'] += vars['delay']
    vars = makeEnd(vars)
    return vars
        
def handleOption(element,vars):
    #recursive function
    if vars['seg'] in vars['ends']:
        del vars['ends'][vars['seg']]
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','style','name','namecol','namestyle'],ignore=['t'])
    vars['maxSeg'] += 1 #this is the next segment to jump to
    tickMem = vars['tick']
    col, style = '',''
    if 'opcol' in element.attrib and element.attrib['opcol'].startswith('!'): #deal with local overrides for the text of the option
        col = element.attrib['opcol'].lstrip('!')
    else:
        col   = getOptionAttribute(vars['opcols'],vars['maxSeg']-vars['seg'],vars['textcol'])
    if 'opstyle' in element.attrib and element.attrib['opstyle'].startswith('!'):
        style = element.attrib['opstyle'].lstrip('!')
    else:
        style = getOptionAttribute(vars['opstyle'],vars['maxSeg']-vars['seg'],vars['style'])
    if 't' not in element.attrib:
        raise xTree.ParseError("Missing required attribute 't' in option at line %d"%element.sourceline)
    write(toOption(element.attrib['t'],col,style,vars,header='OPTION: %s'%element.attrib['t'].upper()))
    vars['trans'].append(toTransition(vars['seg'],vars['maxSeg']))
    vars['tick'] = 0
    segMem = vars['seg']
    vars['seg'] = vars['maxSeg']
    vars = goDeeper(element,vars)
    vars['tick'] = tickMem
    vars['seg'] = segMem
    return vars
    
def handleInstant(element,vars):
    #recursive function, everything within is executed at the same time
    vars = readAttributes(element,vars,['opcol','opstyle','col','style','name','namecol','namestyle'])
    vars['delay'] = 0
    vars = goDeeper(element,vars)
    return vars
    
def handleWrap(element,vars):
    #recursive function, but no upward passing
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','style','name','namecol','namestyle'])
    vars = goDeeper(element,vars)
    return vars
    
def handleDialogue(element,vars):
    #top-layer function
    global maxDiaNum
    vars['ends'] = {} #reinstance, because python does ref passing for dicts
    vars['trans'] = []
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','num','name','style','namecol','namestyle'])
    if vars['num'] == 0:
        vars['num'] = maxDiaNum+1
    maxDiaNum = max(vars['num'],maxDiaNum)
    newDialogue(vars['num'],vars['name'],element.sourceline)
    vars = goDeeper(element,vars)
    for command in vars['trans']:#append the transition block
        write(command)
    write(toCommand(vars['tick'],vars['maxSeg'],'scoreboard players set dNum PD 0',header='#DIALOGUE END'))
    return vars   

def handleTree(element):
    #root function
    vars = {                #init all variables to default:
        'name'   : '',          #name of the speaker
        'namecol': 'white',     #colour of the name
        'namestyle': Style(''), #style of the name
        'num'    : 0,           #num of the dialogue
        'tick'   : 0,           #amount of ticks into the current segment
        'delay'  : 40,          #standard delay between two messages in ticks
        'seg'    : 0,           #segment number in the current dialogue
        'maxSeg' : 0,           #tracker of the highest segment number that has been used in the tree. New segments are made with number maxSeg+1
        'textcol' : 'white',    #colour of the spoken text
        'opcols' : [None],      #colours of the options, a list that is looped
        'opstyle': [Style('')], #styles of the options, also looped list
        'style'  : Style(''),   #text style following MC formatting options, see Style class for more
        'ends'   : {},          #dict of tree leaves, used for convergence
        'trans'  : [],          #list of transitions (either interactive or through convergence), to be appended at the end of the dialogue
    }
    vars = readAttributes(element,vars,['delay','opcol','opstyle','col','style','namecol','namestyle'])
    vars['tick'] = 0 #reading a new delay in collection might have updated the tick, reset
    goDeeper(element,vars,accepted_tags=['dialogue'],upstream_vars=[])#top layer doesn't accept any upstream vars, so each dialogue starts with the same vars.
    
getHandleFunction = { #maps element tags to the handling function (needs to be defined after all the functions
    't'       : handleText,
    'dialogue': handleDialogue,
    'option'  : handleOption,
    'command' : handleCommand,
    'wrap'    : handleWrap,
    'pause'   : handlePause,
    'instant' : handleInstant,
    'concat'  : handleConcat,
}
    
# ------------ ATTRIBUTES ------------#

#update functions have as first argument the vars struct and second the value of the attribute
#and they return a new vars struct with the relevant vars adjusted.
    
def updateDelay(vars,delay):
    oldDelay = vars['delay']
    newDelay = int(delay)
    vars['delay'] = int(delay)
    vars['tick']  = max(0,vars['tick']-(oldDelay-newDelay)) #correct for difference
    return vars
    
def updateOpstyle(vars,opstyle):
    if not opstyle.startswith('!'):
        vars['opstyle'] = [Style(style) if style != 'style' else None for style in opstyle.split(',')]
    return vars
    
def updateOpcol(vars,opcol):
    if not opcol.startswith('!'):
        vars['opcols'] = [str(col) if col != 'col' else None for col in opcol.split(',')]
    return vars
    
def updateCol(vars,col):
    vars['textcol'] = col
    return vars
    
def updateStyle(vars,style):
    vars['style'] = Style(style)
    return vars
    
def updateNum(vars,num):
    global maxDiaNum
    vars['num'] = int(num)
    if vars['num'] > maxDiaNum: maxDiaNum = vars['num']
    return vars
    
def updateName(vars,name):
    vars['name'] = name
    return vars
    
def updateNamecol(vars,namecol):
    vars['namecol'] = namecol
    return vars
    
def updateNamestyle(vars,namestyle):
    vars['namestyle'] = namestyle
    return vars
    
def readSep(vars,sep):
    #reads a separator string, used (only) in concat
    vars['sep'] = sep
    return vars
    
getUpdateAttributeFunction = { #maps attribute names to handling functions
    'delay' : updateDelay,
    'opcol' : updateOpcol,
    'opstyle':updateOpstyle,
    'num'   : updateNum,
    'col'   : updateCol,
    'name'  : updateName,
    'style' : updateStyle,
    'namecol':updateNamecol,
    'namestyle':updateNamestyle,
    'sep'   : readSep,
}
    
# -------------- XML HELPERS -------------#    

def goDeeper(element,vars,accepted_tags=['t','option','command','pause','instant','wrap','concat'],upstream_vars=['maxSeg','seg','ends','tick']):
    #accepted_tags: tags of elements that are allowed to occur at this layer. Defaults to what is accepted in the recursive area of a dialogue tree.
    #upstream_vars: variables that are passed back upstream, while other only go down
    for e in element:
        if e.tag in accepted_tags:
            varsUp = getHandleFunction[e.tag](e,vars.copy())
            for v in upstream_vars:
                vars[v] = varsUp[v]
        else:
            raise xTree.ParseError("Invalid element of type '%s' in '%s' at line %d.\n\n(%s)"%
                    (e.tag,
                    element.tag,
                    e.sourceline,
                    'must be one of: %s'%(str(', '.join(accepted_tags))) if accepted_tags != [] else 'no elements are accepted here'))
    return vars

def readAttributes(element,vars,acceptedAtts,ignore=[]):
    #for all attributes in the element, call the relevant function to update them
    #acceptedAtts: list of attributes that are allowed for a given element
    #ignore: a list of attributes that may exist in an element but who's value is ignored
    #attributes that do not occur in either list but are in the element will produce a warning.
    ignored = []
    for v in element.attrib.keys():
        if v in acceptedAtts:
            vars = getUpdateAttributeFunction[v](vars,element.attrib[v])
        elif v not in ignore:
            ignored.append(v)
    if ignored != []:
        raise xTree.ParseError("Warning: ignored attribute%s %s in %s at line %d.\n\n(Must be one of %s)"%
                ('s' if len(ignored) > 1 else '',
                ', '.join(["'"+s+"'" for s in ignored]),
                element.tag,
                element.sourceline,
                ', '.join(acceptedAtts)))
    return vars
    
def getOptionAttribute(attributes,opNum,default):
    #for a list such as opcols and opstyle, get the relevant item or the default (textcol/textStyle) if it is None
    #opNum should start at 0
    col = attributes[(opNum-1)%len(attributes)]
    if col == None:
        return default
    else:
        return col
    
def doConvergence(vars):
    #for all ends in the ends list, make a command block that syncs that end up with the current segment, then empty the list
    #any leaf node is both a potential end and a point where convergence is necessary
    converged = False
    toremove = []
    for endSeg in vars['ends'].keys():
        if vars['seg'] < endSeg:
            #there are open ends
            converged = True
            endTick = vars['ends'][endSeg]
            vars['trans'].append(toCommand(endTick,endSeg,'scoreboard players set dNewSeg PD %d'%(vars['maxSeg']+1),header='CONVERGENCE %d ==> %d'%(endSeg,vars['maxSeg']+1)))
            toremove.append(endSeg)
    for endSeg in toremove:
        del vars['ends'][endSeg]
    if converged:
        vars['maxSeg'] += 1
        vars['seg'] = vars['maxSeg']
        vars['tick'] = 0
    return vars
    
def makeEnd(vars):
    #make a new end for this segment
    vars['ends'][vars['seg']] = vars['tick']
    return vars
    
# ------------- COMMANDS -------------#

def toCommand(time,seg,command,header=''):
    if header != '':
        header = '#%s\n'%header
    return  '%s'%header +\
            'scoreboard players remove dTim PD %d\n'%time +\
            'scoreboard players remove dSeg PD %d\n'%seg +\
            'execute if score dSeg PD = zero PD run execute if score dTim PD = zero PD run %s\n'%command +\
            'scoreboard players operation dSeg PD = dOldSeg PD\n' +\
            'scoreboard players operation dTim PD = dOldTim PD\n\n'

def toTransition(segFrom,segTo):
    return  '#TRANSITION %d ==> %d\n'%(segFrom,segTo) +\
            'scoreboard players remove dSeg PD %d\n'%segFrom +\
            'execute if score dSeg PD = zero PD run scoreboard players operation dNewSeg PD = @a[scores={dSeg=%d}] dSeg\n'%(segTo) +\
            'scoreboard players operation dSeg PD = dOldSeg PD\n\n'

def toMessage(text,vars,header=''):
    #construct the basic (non-interactable) tellraw message for a command block
    compounds = constructCompounds(text,vars)
    return toCommand(vars['tick'],vars['seg'],'tellraw @a ' + toTellraw(compounds),header)
    
def constructCompounds(text,vars):
    compounds = []
    if vars['name'] != '': compounds.append(TextCompound('[%s] '%vars['name'],vars['namecol'],vars['namestyle']))
    splitOnFormat = [s for s in re.split(u'(\xa7.)',text) if s != '']
    workcol = vars['textcol']
    workstyle = vars['style'].copy()#local version of col and style that only apply to this text
    colmem = workcol
    stymem = workstyle.copy()
    for fs in splitOnFormat:
        if fs.startswith(u'\xa7'):
            #this is a formatting character, adjust vars
            workcol,workstyle = handleFormattingCode(fs[1],workcol,workstyle,colmem,stymem)
        else:
            splitOnSelectors = [x for x in re.split('(@.\[.+?\]|@.)',fs) if x != '']
            for ss in splitOnSelectors:
                if ss.startswith('@'):
                    #this is a selector
                    compounds.append(SelectorCompound(ss,workcol,workstyle))
                else:
                    compounds.append(TextCompound(ss,workcol,workstyle))
    return compounds
    
def constructOptionCompounds(text,workcol,style,clickevent):
    splitOnFormat = [s for s in re.split(u'(\xa7.)',text) if s != '']
    workstyle = style.copy()#local version of col and style that only apply to this text
    colmem = workcol
    stymem = workstyle.copy()
    compounds = [TextCompound('[',colmem,stymem,clickevent)]
    for fs in splitOnFormat:
        if fs.startswith(u'\xa7'):
            #this is a formatting character, adjust vars
            workcol,workstyle = handleFormattingCode(fs[1],workcol,workstyle,colmem,stymem)
        else:
            splitOnSelectors = [x for x in re.split('(@.\[.+?\]|@.)',fs) if x != '']
            for ss in splitOnSelectors:
                if ss.startswith('@'):
                    #this is a selector
                    #TODO (LATER VERSION): If Mojang fixes issue MC-55493, use line below to enable selectors in option (that have a working clickEvent).
                    compounds.append(TextCompound(ss,workcol,workstyle,extra=clickevent))
                    #compounds.append(SelectorCompound(ss,workcol,workstyle,extra=clickevent))
                else:
                    compounds.append(TextCompound(ss,workcol,workstyle,extra=clickevent))
    compounds.append(TextCompound(']',colmem,stymem,clickevent))
    return compounds
        
class UnknownFormattingCodeError(Exception):
    pass
        
def handleFormattingCode(mode,workcol,workstyle,defcol,defstyle):
    #take a formatting code (§x) and update vars accordingly
    if   mode == '0': workcol = 'black'
    elif mode == '1': workcol = 'dark_blue'
    elif mode == '2': workcol = 'dark_green'
    elif mode == '3': workcol = 'dark_aqua'
    elif mode == '4': workcol = 'dark_red'
    elif mode == '5': workcol = 'dark_purple'
    elif mode == '6': workcol = 'gold'
    elif mode == '7': workcol = 'gray'
    elif mode == '8': workcol = 'dark_gray'
    elif mode == '9': workcol = 'blue'
    elif mode == 'a': workcol = 'green'
    elif mode == 'b': workcol = 'aqua'
    elif mode == 'c': workcol = 'red'
    elif mode == 'd': workcol = 'light_purple'
    elif mode == 'e': workcol = 'yellow'
    elif mode == 'f': workcol = 'white'
    elif mode == 'k': workstyle.obfuscated = True
    elif mode == 'l': workstyle.bold = True
    elif mode == 'm': workstyle.strikethrough = True
    elif mode == 'n': workstyle.underlined = True
    elif mode == 'o': workstyle.italic = True
    elif mode == 'r':
        workcol = defcol
        workstyle = defstyle.copy()
    else: raise UnknownFormattingCodeError("Encountered unknown formatting code %s"%mode)
    return workcol,workstyle
        
             
class TextCompound():
    #JSON compound of text
    def __init__(self,text,colour,style,extra=''):
        self.text = text
        self.colour = colour
        self.style = style.copy()
        self.extra = extra
        
    def encode(self):
        return '{"text":"%s"%s%s%s}'%(
            self.text,
            ',"color":"%s"'%(self.colour),
            self.style.toTellrawProperties(),
            self.extra)
            
    def __str__(self):
        return self.text
            
class SelectorCompound():
    #JSON compound that consists of a selector
    def __init__(self,selector,colour,style,extra=''):
        self.selector = selector.encode('utf-8')
        self.colour = colour
        self.style = style.copy()
        self.extra = extra
        
    def encode(self):
        return '{"selector":"%s"%s%s%s}'%(
            self.selector,
            ',"color":"%s"'%(self.colour),
            self.style.toTellrawProperties(),
            self.extra)
            
    def __str__(self):
        return self.selector
             
def toTellraw(compounds):
    #take a list of JSON compounds and produce the entire tellraw JSON argument
    return '[%s]'%','.join([c.encode() for c in compounds])        
    
def toOption(text,colour,style,vars,header=''):
    #This command needs the dialogue number and old segment to make sure the options are only clickable at one moment
    compounds = constructOptionCompounds(text,colour,style,',"clickEvent":{"action":"run_command","value":"/trigger dSeg set %d"}'%vars['maxSeg'])
    return toCommand(vars['tick'],vars['seg'],'tellraw @a ' + toTellraw(compounds),header)

#--------------- WRITING ---------------#

def write(lines):
    dialogueFile.write(lines)

def newDialogue(diaNum,name,line):
    #Starts a new dialogue file
    global dialogueFile, diaNums
    if 'dialogueFile' in globals():#text whether variable is initiated
        dialogueFile.close()
    dialogueFile = open(os.path.join(targetpath,'data/projectdialogue/functions','dialogue%d.mcfunction'%(diaNum)),'w')
    write("#DIALOGUE NUMBER: %d\n#DIALOGUE NAME:   %s\n#SOURCE LINE:     %d\n\n"%(diaNum,name,line))
    # print('Assigning number %d to dialogue \'%s\' at line %d'%(diaNum,name,line))
    if diaNum in diaNums:
        raise SimpleTerminationException("Number %d used for multiple dialogues! A dialogue number must be unique!"%diaNum)
    else:
        diaNums[diaNum] = name
    # print("Current Dialogue: %s"%os.path.join(targetpath,'data/projectdialogue/functions','dialogue%d.mcfunction'%(diaNum)))
    
def initDirectories(): 
    #create directories and place the unchanging files there
    if os.path.exists(targetpath): 
        try:
            shutil.rmtree(targetpath) #remove old instance of the file structure #TODO query user for target dir?
        except OSError:
            raise SimpleTerminationException('Can\'t remove old instance of PD files. If you have any files/directories opened, close them and try again')
    os.makedirs(os.path.join(targetpath,'data/minecraft/tags/functions'),exist_ok=True)
    os.makedirs(os.path.join(targetpath,'data/projectdialogue/functions'),exist_ok=True)
    #create constant files
    with open(os.path.join(targetpath,'pack.mcmeta'),'w') as f:
        f.write('{\n\t"pack": {\n\t\t"pack_format": 1,\n\t\t"description": "Project: DIALOGUE"\n\t}\n}')
    with open(os.path.join(targetpath,'data/minecraft/tags/functions/load.json'),'w') as f:
        f.write('{\n\t"values": [\n\t\t"projectdialogue:pdload"\n\t]\n}')
    with open(os.path.join(targetpath,'data/minecraft/tags/functions/tick.json'),'w') as f:
        f.write('{\n\t"values": [\n\t\t"projectdialogue:pdtick"\n\t]\n}')
    with open(os.path.join(targetpath,'data/projectdialogue/functions/pdload.mcfunction'),'w') as f:
        f.write('scoreboard objectives add PD dummy "PD"\n' +\
                'scoreboard players set zero PD 0\n' +\
                'scoreboard objectives add dSeg trigger "dSeg"\n' +\
                'gamerule sendCommandFeedback false') 
                #debug features
                # 'scoreboard objectives setdisplay sidebar PD\n' +\
                # 'scoreboard objectives setdisplay list dSeg\n' +\
    
def constructTickFile(diaNums):
    with open(os.path.join(targetpath,'data/projectdialogue/functions/pdtick.mcfunction'),'w') as f:
        #tick operations: 1) increment timer, 2) check if number has changed, if so reset timer and segment, 3) check if newSeg was assigned, if so reset timer and update seg, 4) update all memory variables
        f.write('scoreboard players add dTim PD 1\n' +\
                'execute unless score dNum PD = dOldNum PD run scoreboard players set dTim PD -1\n' +\
                'execute unless score dNum PD = dOldNum PD run scoreboard players set dSeg PD 0\n' +\
                'execute unless score dNum PD = dOldNum PD run scoreboard players set @a dSeg 0\n' +\
                'execute unless score dNewSeg PD = zero PD run scoreboard players set dTim PD -1\n' +\
                'execute unless score dNewSeg PD = zero PD run scoreboard players operation dSeg PD = dNewSeg PD\n' +\
                'execute unless score dNewSeg PD = zero PD run scoreboard players set dNewSeg PD 0\n' +\
                'scoreboard players operation dOldNum PD = dNum PD\n' +\
                'scoreboard players operation dOldSeg PD = dSeg PD\n' +\
                'scoreboard players operation dOldTim PD = dTim PD\n\n')
        #5) dialogue switch
        f.write('#ACTIVATE CURRENT DIALOGUE (this currently the most exact/efficient method to check hardcoded values, let\'s hope MC eventually adds a feature for this)\n')
        for n in diaNums.keys():
            f.write('scoreboard players remove dNum PD %d\n'%n +\
                    'execute if score dNum PD = zero PD run function projectdialogue:dialogue%d\n'%n +\
                    'scoreboard players operation dNum PD = dOldNum PD\n\n')
        #6) post tick cleanup, preps trigger for user interaction
        f.write('scoreboard players set @a[scores={dSeg=1..}] dSeg 0\n' +\
                'scoreboard players enable @a dSeg')

#------------- RUN ---------------#

root = tk.Tk()
root.geometry("800x800")
root.iconbitmap("logo.ico")
root.title("Project DIALOGUE")
root.configure(background="gray24")

def loadXMLFile():
    xmlFile = filedialog.askopenfilename(initialdir = os.getcwd(),title = "Select Project DIALOGUE XML file",filetypes = (("xml files","*.xml"),("all files","*.*")))
    setText(xmlFileText,xmlFile)
    
def askTargetDir():
    targetdir = filedialog.askdirectory(initialdir = os.getcwd(),title = "Assign a target directory")
    setText(targetDirText,targetdir)
    
def setText(textwidget,newtext):
    #replace the text in textwidget with newtext
    textwidget.delete(1.0,tk.END)
    textwidget.insert(tk.END,newtext)
    
def go():
    global targetpath, maxDiaNum, diaNums, dialogueFile 
    maxDiaNum = 0
    diaNums = {}
    try:
        targetpath = os.path.join(targetDirText.get(1.0, tk.END).rstrip('\n'),'PD')
        filename = xmlFileText.get(1.0, tk.END).rstrip('\n')
        initDirectories()
        if filename != None:
            root = xTree.parse(filename,parser=LineNumberingParser()).getroot()
            handleTree(root)
            dialogueFile.close()
            constructTickFile(diaNums)
        messagebox.showinfo("Done!","Project: DIALOGUE succesfully completed. The following numbers were assigned (you can also find these mappings in each respective dialogue file in the datapack):\n" + '\n'.join(['%d: %s'%(num,name) for (num, name) in diaNums.items()]))
    except SimpleTerminationException as e:
        messagebox.showerror("Error",str(e))
    except xTree.ParseError as e:
        messagebox.showerror("XML Error",str(e))
    except UnknownFormattingCodeError as e:
        messagebox.showerror("Minecraft formatting code error",str(e))
    except Exception as e:
        messagebox.showerror("Unknown error",str(e))
        
header = tk.PhotoImage(file="header.png")
headerLabel = tk.Label(image=header, borderwidth=0)
headerLabel.pack()

hline1=tk.Frame(root,height=4,width=50,bg="black", borderwidth=8, relief="groove")
hline1.pack(fill=tk.X)

fontButtons = ("fixedsys", 24)
fontTexts   = ("fixedsys", 18)

xmlFileButton = tk.Button(root, text="Browse XML file", command = loadXMLFile, borderwidth=4, bg="gray25", fg="gainsboro", font=fontButtons)
xmlFileText = tk.Text(root, bg="gray35", fg="gainsboro", borderwidth=8, relief="groove", font=fontTexts, height=3, padx=20, wrap=tk.CHAR)
setText(xmlFileText, "")
xmlFileButton.pack(pady=10)
xmlFileText.pack(pady=10,padx=10)

hline2=tk.Frame(root,height=4,width=50,bg="black", borderwidth=8, relief="groove")
hline2.pack(fill=tk.X)

targetDirButton = tk.Button(root, text="Assign a target directory", command = askTargetDir, borderwidth=4, bg="gray25", fg="gainsboro", font=fontButtons)
targetDirText = tk.Text(root, bg="gray35", fg="gainsboro", borderwidth=8, relief="groove", font=fontTexts, height=3, wrap=tk.CHAR)
setText(targetDirText, os.getcwd())
targetDirButton.pack(pady=10)
targetDirText.pack(pady=10,padx=10)

hline3=tk.Frame(root,height=4,width=50,bg="black", borderwidth=8, relief="groove")
hline3.pack(fill=tk.X)

goButton = tk.Button(root, text="GO!", command = go, bg="gray25", fg="gainsboro", borderwidth=8, font=("fixedsys", 30,"bold"))
goButton.pack(pady=20)

root.mainloop()
