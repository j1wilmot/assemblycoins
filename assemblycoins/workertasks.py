import requests
import json
import addresses
import transactions
import bitsource
import databases
import email_commands
import os

def getblock_blockchain(blockn):
  try:
    url='http://blockchain.info/block-height/'+str(blockn)+'?format=json'
    data=requests.get(url)
    jsondata=json.loads(data.content)
    answer={}
    for x in jsondata['blocks']:
      if x['main_chain']==True:
        answer=x
    return answer
  except:
    print "COULD NOT GET BLOCK FROM BLOCKCHAIN.info"

def getblock_toshi(blockn):
  try:
    url='https://bitcoin.toshi.io/api/v0/blocks/'+str(blockn)
    data=requests.get(url)
    jsondata=json.loads(data.content)
    answer={}
    for x in jsondata['blocks']:
      if x['main_chain']==True:
        answer=x
    return answer
  except:
    print "COULD NOT GET BLOCK FROM TOSHI"
    return {}

def opreturns_in_block(blockn):
  data=getblock_blockchain(blockn)
  results=[]
  if not data is None:
    if 'tx' in data:
      txs=data['tx']
      counter=0
      for tx in txs:
        message=''
        counter=counter+1
        n=0
        for out in tx['out']:
          script=out['script']
          if script[0:2]=='6a':
            m=script[2:len(script)]
            m=m.decode('hex')
            print m
            message=m[1:len(m)]
            amount=0
            for x in tx['inputs']:
              if 'prev_out' in x:
                amount=amount+x['prev_out']['value']
            results.append([str(tx['hash'])+":"+str(n),message, amount])
          n=n+1
  return results

def oa_in_block(blockn):
  opreturns=opreturns_in_block(blockn)
  oatxs=[]
  for x in opreturns:
    if x[1][0:2]=='OA':
      parsed=bitsource.parse_colored_tx(x[1], x[0])
      #take txhash, find address corresponding to parsed metadata colored behavior
      oatxs.append([x[0],parsed,x[2]])  #TXHASH_WITH_INDEX, METADATA PARSED,  BTC CONTENT,  OUTPUT ADDRESSES as array
  return oatxs

def output_db(blockn):
    #ADD OUTPUTS TO DB assuming correctness
    txdata=oa_in_block(blockn)
    if not txdata is None:
      for tx in txdata:
        #ISSUED
        if len(tx)>0:
          if 'issued' in tx[1]:
            for txissued in tx[1]['issued']:
              coloraddress = txissued['color_address']
              btc= str(txissued['btc'])
              coloramt = str(txissued['quantity'])
              spent=str(False)
              spentat=""
              destination=str(txissued['destination_address'])
              txhash_index=str(txissued['txhash_index'])
              txhash = txhash_index[0:len(txhash_index)-2]
              blockmade=str(blockn)
              prev_input=txissued['previous_inputs']
              databases.add_output(btc, coloramt, coloraddress, spent, spentat, destination, txhash, txhash_index, blockmade, prev_input)

                  #EDIT COLOR OVERVIEW DATA
              oldamount=databases.read_color(coloraddress)
              if len(oldamount)==0:  #COLOR DOES NOT EXIST YET
                source_address=prev_input[7:len(prev_input)]
                databases.add_color(coloraddress, source_address, coloramt, "color_name")
              else:
                oldamount=oldamount[0][2]
                databases.edit_color(coloraddress, int(oldamount)+int(coloramt))

                #TRANSFERRED
            for txtransfer in tx[1]['transferred']:
              coloraddress="illegitimate"
              btc=str(txtransfer['btc'])
              coloramt=str(txtransfer['quantity'])
              spent=str(False)
              spentat=""
              destination=txtransfer['destination_address']
              txhash_index=txtransfer['txhash_index']
              txhash=txhash_index[0:len(txhash_index)-2]
              blockmade=str(blockn)
              prev_input=txtransfer['previous_inputs']
              databases.add_output(btc, coloramt, coloraddress, spent, spentat, destination, txhash, txhash_index, blockmade, prev_input)

      recentlyaddedtxs=databases.dbexecute("SELECT txhash FROM OUTPUTS WHERE blockmade="+str(blockn)+";", True)
      print "recently added txs  "
      print recentlyaddedtxs
      print ""
      for tx in recentlyaddedtxs:
        txhash=tx[0]
        totalin=0
        inputs=databases.dbexecute("SELECT previous_input from outputs where txhash='"+txhash+"';",True)

        if len(inputs)>0:
          inputs=inputs[0]

          for inp in inputs:
            if inp[0:7]=="source:": #WAS ISSUED, need not be checked
              totalin=999999999999
            else:
              inp=inp.split("_")
              inp=inp[0:len(inp)-1]
              print "MY INPUTS IN TRANSFER "
              print inp
              print ""
              for x in inp:
                dbstring="SELECT color_amount from outputs where txhash_index='"+x+"';"
                colinps=databases.dbexecute(dbstring,True)
                for colinp in colinps:
                  totalin=totalin+colinp[0]

        #THEN SUM TOTAL OUT
        outps=databases.dbexecute("SELECT color_amount from outputs where blockmade="+str(blockn)+" and txhash='"+txhash+"'", True)
        totalout=0
        for outp in outps:
          totalout=totalout+outp[0]
        #IF TOTALIN>= TOTAL OUT, its OK, else, SPENT ALL OUTPUTS AND UNSPEND ALL INPUTS
        print "IN: "+str(totalin)+"  OUT: "+str(totalout)+"   for tx: "+str(tx)
        if totalout<=totalin:
          #everything OK
          print "legit tx: "+str(tx)

          #SPEND INPUTS FINALLY
          inputs=databases.dbexecute("SELECT previous_input from outputs where txhash='"+txhash+"';",True)

          for inp in inputs:
            for x in inp:
              if not x[0:7]=="source:":
                x=x.split("_")
                x=x[0:len(x)-1]
                print x

                #GET COLOR OF PREVIOUS INPUTS
                thecolor=databases.dbexecute("SELECT color_address from outputs where txhash_index='"+x[0]+"';",True)
                if len(thecolor)>0:
                  thecolor=thecolor[0][0]
                else:
                  thecolor="unknown"
                #SET COLOR
                databases.dbexecute("UPDATE outputs set color_address='"+thecolor+"' where txhash='"+txhash+"';",False)

                for y in x:
                  databases.spend_output(str(y), txhash,blockn)
                  print "SPENDING: "+str(y)
        else:
          print "ILLEGITIMATE TX DETECTED: "+str(tx)

    #databases.dbexecute("delete from outputs * where color_address='illegitimate';",False)

def tx_queue_batches():
  current_block=bitsource.get_current_block()
  distinct_senders=databases.dbexecute("select distinct from_public from tx_queue where success='False';",True)

  for sender in distinct_senders:
    sender=sender[0]
    colors=databases.dbexecute("select distinct source_address from tx_queue where from_public='"+sender+"';", True)
    for color in colors:

      if color[0]=='': #IS BTC TRANSFER NOT COLORED
        txs=databases.dbexecute("select * from tx_queue where from_public='"+str(sender)+"' and success='False' and source_address='';",True)

        for x in txs:
          public_address=x[0]
          private_key=x[1]
          amount=x[5]*0.00000001
          destination=x[2]
          fee=os.environ['STANDARD_BTC_FEE']
          #print str(public_address)+" / "+str(amount)+ " / "+str(destination)+" / "+str(fee)
          tx=transactions.make_raw_transaction(public_address,amount,destination, fee)
          try:
              tx2=transactions.sign_tx(tx, private_key)
          except:
              tx2=''
          tx3=transactions.pushtx(tx2)
          if len(tx3)>0:
            databases.dbexecute("update tx_queue set success='True', txhash='"+str(tx3)+"' where randomid='"+str(x[10])+"'", False)

      else:
        color_needed=0
        txs=databases.dbexecute("select * from tx_queue where from_public='"+sender+"' and success='False' and source_address='"+color[0]+"';",True)
        coloramt_array=[]
        dest_array=[]
        fromaddr=sender
        btc_needed=0
        feestotal=0
        rowlist=[]

        if len(txs)>10:  #limit outputs per TX
          txs=txs[0:10]

        for tx in txs:
          color_needed=color_needed+tx[5]
          fee_each=float(tx[3])*0.00000001
          btc_needed=btc_needed+int(transactions.dust*100000000) #INTEGER, IN SATOSHIs
          feestotal=feestotal+int(tx[3])

          if tx[5]>0:
            dest_array.append(tx[2])
            coloramt_array.append(tx[5])

          privatekey=tx[1]
          othermeta="multitransfer"
          rowlist.append(tx[10])

        if feestotal>10000:
          feestotal = 10000 *(1+len(txs)/5)
        btc_needed=btc_needed+feestotal

        sourceaddress=color[0]
        coloraddress=databases.first_coloraddress_from_sourceaddress(sourceaddress)
        btc_needed=float(btc_needed)/100000000
        inputs=transactions.find_transfer_inputs(fromaddr, coloraddress, color_needed, btc_needed)
        inputcolortamt=inputs[1]
        inputs=inputs[0]

        if len(txs)>0:
            if len(dest_array)>6:
              fee_each=fee_each*(1+len(dest_array)/6)

            print str(fromaddr)+ " / "+ str(dest_array) + " / "+str(fee_each)+ " / "+str(privatekey)+" / " +str(sourceaddress)+" / "+str(coloramt_array)+" / "+str(othermeta)
            result=transactions.transfer_tx_multiple(fromaddr, dest_array, fee_each, privatekey, sourceaddress, coloramt_array, othermeta)
            try:
              result=result[0]
            except:
              print result
              result=None
            #except:
            #  print "ERROR processing queued TX from "+str(fromaddr)
          #    result=None

            if result is None:
              print "No response heard from Bitcoin Network"
            elif not str(result)=="None":
              print "HEARD TX RESULT: "+str(result)

              for id in rowlist:
                dbstring2="update tx_queue set txhash='"+str(result) +"', success='True' where randomid='"+str(id)+"';"
                print dbstring2
                databases.dbexecute(dbstring2,False)

def tx_queue():
  dbstring="select * from tx_queue where success='False';"
  txs=databases.dbexecute(dbstring,True)
  print txs
  for tx in txs:
    fromaddr=tx[0]
    destination=tx[2]
    fee=float(tx[3])*0.00000001
    privatekey=tx[1]
    source_address=tx[4]
    coloramt=tx[5]
    randomid=tx[10]
    othermeta="transfer"
    try:
      result=transactions.transfer_tx(fromaddr, destination, fee, privatekey, source_address, coloramt, othermeta)
    except:
      print "ERROR processing queued TX from "+str(fromaddr)
      result=None
    result=result[0]
    if result is None:
      print "No response heard from Bitcoin Network"
      firsttriedatblock=tx[6]
      if firsttriedatblock==-1:
        dbstring="update tx_queue set first_tried_at_block='"+str(current_block)+"' where randomid='"+randomid+"';"
        databases.dbexecute(dbstring,False)
      elif current_block-firsttriedatblock>500:
        dbstring="delete from tx_queue * where randomid='"+randomid+"';"
        databases.dbexecute(dbstring,False)

    elif len(str(result))>10:
      print "HEARD TX RESULT: "+str(result)
      dbstring2="update tx_queue set txhash='"+str(result) +"', success='True' where randomid='"+randomid+"';"
      databases.dbexecute(dbstring2,False)
      print dbstring2
      response={}
      response['transaction_hash']=result
      response=json.dumps(response)
      postresponse=requests.post(tx[9], data=response)
      print "SENDING POST TO "+str(tx[9])+ " WITH DATA= "+str(response)
      print "RESPONSE HEARD TYPE "+str(postresponse.status_code)
      print "RESPONSE CONTENTS: "+str(postresponse.content)

def blocks_outputs(blockend):
  lastblockprocessed=databases.dbexecute("SELECT * FROM META;",True)
  currentblock=bitsource.get_current_block()
  if blockend>currentblock:
    blockend=currentblock
  for i in range(lastblockprocessed[0][0]+1,blockend+1):
    add_output_db(i)
    print "processed block "+str(i)
    databases.dbexecute("UPDATE META SET lastblockdone='"+str(i)+"';",False)

def more_blocks(moreblocks):
    currentblock=int(bitsource.get_current_block())
    lastblockprocessed=databases.dbexecute("SELECT * FROM META;",True)
    nextblock=lastblockprocessed[0][0]+moreblocks

    print "starting block " +str(currentblock)
    print "nextblock "+str(nextblock)

    if nextblock>currentblock:
      nextblock=currentblock

    if lastblockprocessed[0][0]<currentblock:
      for i in range(lastblockprocessed[0][0]+1, nextblock+1):
        if i<=currentblock:
          output_db(i)
          print "processed block "+str(i)
          databases.dbexecute("UPDATE META SET lastblockdone='"+str(i)+"';",False)

def checkaddresses():
  dbstring="SELECT * FROM ADDRESSES WHERE amount_withdrawn=0;"
  addresslist=databases.dbexecute(dbstring,True)
  print addresslist

  for address in addresslist:
    unspents=addresses.get_unspent(address[0])
    value=0
    for x in unspents:
      value=value+x['value']
    print "currently available in "+str(address[0])+" : "+str(value/100000000)

    if value>=address[2] and address[3]<address[2]:
      #makenewcoins
      fromaddr=address[0]
      colornumber=address[6]
      colorname=address[5]
      destination=address[7]
      fee_each=0.00005
      private_key=address[1]
      ticker=address[9]
      description=address[8]

      try:
        txdata=transactions.make_new_coin(fromaddr, colornumber, colorname, destination, fee_each, private_key, description)
      except:
        print "ERROR CREATING NEW COIN"
        print str(fromaddr)+" / "+str(colornumber)+" / "+str(colorname)+" / "+str(destination)+" / "+str(fee_each)+" / "+str(private_key)+" / "+str(description)

      try:
        txhash=txdata['transaction_hash']
      except:
        txhash = "Error"
        print "ERROR reading txdata"
        print txdata

      txhash=txhash+":0" #issuance always first output
        #mark as completed
      if txhash=="None:0":
        k=1 #do nothing
      else:
        databases.edit_address(fromaddr, value, value, colornumber)
        their_email=address[9]
        email_commands.email_creation(str(their_email), str(colorname), str(colornumber), str(description), str(txhash))
        databases.dbexecute("insert into colors (source_address, color_name) values ('"+fromaddr+"','"+colorname+"');",False)
      # except:
      #   print "something went wrong AFTER make_new_coin"
      #   print txdata
      #   print ''

      #add entry to colors db
      # #referencehex=bitsource.tx_lookup(specific_inputs)
      # color_address=bitsource.script_to_coloraddress()
      #databases.add_color(color_address, fromaddr, colornumber, colorname)

      #EMAIL THEM

      #add entry to outputs db

      #send profits elsewhere
      # markup=1.0
      # extra=transactions.creation_cost(colornumber, colorname, ticker, description, fee_each, markup)*(markup/(1.0+markup))
      # tx=transactions.make_raw_transaction(fromaddr,extra,profit_address, 0.00003)
      # tx2=transactions.sign_tx(tx)
      # transactions.pushtx(tx2)

def verify_colors():
  unknowns=databases.dbexecute("select * from outputs where spent='false' and color_address='unknown';",True)
  for unknown in unknowns:
    previous_inputs=unknown[9]
    previous_inputs=previous_inputs.split("_")
    previous_inputs=previous_inputs[0:len(previous_inputs)-1]

    coloraddress=''

    for previous_input in previous_inputs:
      data=databases.dbexecute("select color_address from outputs where txhash_index='"+previous_input+"';", True)
      try:
        data=data[0][0]
      except:
        data='unknown'
      coloraddress=data
    dbstring="update outputs set color_address='"+coloraddress+"' where txhash_index='"+unknown[7]+"';"
    print dbstring
    databases.dbexecute(dbstring,False)

def read_color_names():
  unnamed_colors=databases.dbexecute("select * from colors where color_name='color_name';",True)
  totallength=len(unnamed_colors)
  n=0
  for unnamed_color in unnamed_colors:
    #lookup metadata on blockchain
    address=unnamed_color[1] #the source_address
    result=addresses.read_opreturns_sent_by_address(address)
    name="color_name"
    print "color: "+str(n)+" / "+str(totallength)
    n=n+1
    try:
      name=json.loads(result)
      name=name['name']
      databases.dbexecute("update colors set color_name='"+name+"' where source_address='"+address+"';", False)
    except:
      print "no name found for source: "+str(address)

def check_for_misspents(block_height_start, block_height_end):   #BLOCKHEIGHT INPUT MEANS CHECK FOR OUTPUTS SINCE THIS BLOCK HEIGHT
  txs=databases.dbexecute("select * from outputs where blockmade>="+str(block_height_start) +" and blockmade<="+str(block_height_end)+";",True)
  for tx in txs:
    txhash_index=tx[7]
    txhash_index=txhash_index.split(":")
    txhash=txhash_index[0]
    index=int(txhash_index[1])

    spent=bitsource.check_if_output_misspent(txhash, index)
    if spent:
      print "output is spent: "+str(txhash_index)
      index=str(index)
      #MARK AS SPENT IN OUTPUTS DB,  MARK spent_at_transactionhash = "DESTROYED"
      dbstring="UPDATE outputs SET spent=true, spent_at_txhash='destroyed' where txhash_index='"+str(txhash)+":"+str(index)+"';"
      databases.dbexecute(dbstring,False)
      print "MISSPENT TX DISCOVERED: "+str(txhash)+":"+str(index)
