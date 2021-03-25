import os, re
from datetime import datetime
import pandas as pd
from SMRTDB import Session, File, Reading

# File handler for .SMRT files (default folder .data/)
class SMRT:

    def __init__(self, path='data/'):

        self.path = path # a different path could be passed in
        self.files = self.get_files()
        self.valid = False
        self.headers = pd.DataFrame()
        self.readings = pd.DataFrame()
        self.last_file_ref = None
        self.session = Session()
    
    # get all the SMRT file names in the default data folder
    def get_files(self):
        files = {str(x[0]):x[1] for x in enumerate(sorted(os.listdir(self.path)), 1) if x[1].endswith('.SMRT')}
        print("Following SMRT files to be parsed and uploaded:")
        for k,v in files.items():
            print(k,v)
        return [self.path+x for x in files.values()]
    
    def parse(self):
        # iterate all files to get headers and readings
        for f in self.files:
            # validate file structure first
            self.validate(f)
            # if valid then get the data
            self.get_header(f)
            self.get_readings(f)
            # after parse reset valid lable to defaut False
            self.valid=False
        # overwrite duplicated readings so data is ready for db insert
        self.readings.sort_values('FileRef', inplace=True)
        self.readings.drop_duplicates(subset=['MeterID','Date','Time'],keep='last',inplace=True)
        self.readings.reset_index(inplace=True)

    def validate(self, file=None):
        # validate SMRT file 'Record Structure'
        if not self.valid:
            df = pd.read_csv(file, header=None, names=['Record'], usecols=[0])
            structure = df['Record'].unique()
            # Check if the records starts with 'HEARDR' ends with 'TRAIL'
            structrue_check = (structure == ['HEADR', 'CONSU', 'TRAIL'])
            if structrue_check.all():
                self.valid = True
            else:
                print(f'{file} Record Structure is INVALID')
                print(f'please check {structrue_check[~structrue_check]}.')
        else:
            print('SMRT Record structur is VALID.')
       
    def get_header(self, file=None):
        # only get data when valid otherwise pass
        if self.valid:
            cols = ['Record', 'Type', 'CompanyID', 'Date', 'Time', 'Ref']
            dtypes = {
                'Record': str,
                'Type': str,
                'CompanyID': str,
                'Date': str,
                'Time': str,
                'Ref': str
            }
            try:
                df = pd.read_csv(file, header=None, names=cols, dtype=dtypes, nrows=1)
                df.loc[0,'Ref'] = re.match(r'(PN|DV)\d{6}', df.loc[0,'Ref']).group()
                # add the paresed header into the self.headers
                self.headers = self.headers.append(df, ignore_index=True)
                # Ref of file is needed when parsing readings data
                self.last_file_ref = df.loc[0,'Ref']
                print(df)
            except Exception as e:
                print(e)
                print('Error at SMRT HEADR')
    
    def get_readings(self, file=None):
        # only get data when valid otherwise pass
        if self.valid:
            cols = ['Record', 'MeterID', 'Date', 'Time', 'Reading']
            dtypes = {
                'Record': str,
                'MeterID': str,
                'Date': str,
                'Time': str,
                'Reading': float
            }
            df = pd.read_csv(file, header=None, names=cols, dtype=dtypes, skiprows=1, skipfooter=1, engine='python')
            # add Ref in readings dataset
            df['FileRef'] = self.last_file_ref
            # add readings into self.readings
            self.readings = self.readings.append(df, ignore_index=True)

    def db_insert(self):

        self.insert_headers()
        self.insert_readings()
    
    def insert_headers(self, entry=File):
        # iterate each row (each SMRT file header)
        for _, row in self.headers.iterrows():
            ts_string = row['Date'] + ':' + row['Time']
            ts = datetime.strptime(ts_string, '%Y%m%d:%H%M%S')
            dbrow = entry(ref=row['Ref'], type=row['Type'], companyid=row['CompanyID'], createdts=ts)
            # add the data in database session to be inserted
            self.session.add(dbrow)
        try:
            # submit the change in database
            self.session.commit()
            print(f'{self.headers.shape[0]} File headers inserted into TABLE files.')
        except Exception as e:
            print(e)
            print('ERROR: insert_header session rolled back.')
        else:
            # if failed restore the change
            self.session.rollback()
    
    def insert_readings(self, entry=Reading):
        # iterate each meter reading 
        for _, row in self.readings.iterrows():
            # get the file record which this reading should be linked to
            file = self.session.query(File).filter_by(ref=row['FileRef']).one()
            # get the timestamp and also keep the date which is used frequently
            ts_string = row['Date'] + ':' + row['Time']
            ts = datetime.strptime(ts_string, '%Y%m%d:%H%M')
            dbrow = entry(meterid=row['MeterID'], readingdate=row['Date'],
                            timestamp=ts, value=row['Reading'], filename=file)
            # add the data in database session to be inserted
            self.session.merge(dbrow)
        
        try:
            # submit the change in database
            self.session.commit()
            print(f'{self.readings.shape[0]} meter readings inserted into TABLE readings.')
        except Exception as e:
            print(e)
            print(f"insert reading data for file {file.ref} \nsession rolled back.")
        else:
            # if failed restore the change
            self.session.rollback()


class View:
    # Defaul table is readings
    def __init__(self, table=Reading):
        if table:
            self.table = table
        # create the database query session
        self.session = Session()
        
    
    def to_dataframe(self, field=None, value=None):
        # perform filtered query if filed/value both provided
        if field and value:
            s = self.session.query(self.table).filter(getattr(self.table, field)==value)
        else:
            # if None perform select all by default
            s = self.session.query(self.table)
        # return the query result into dataframe
        return pd.read_sql(s.statement, self.session.bind)
        


# Question 3 How many files have we recieved? 
parser = SMRT()
# To get all the availlable data
parser.parse()
# Headers
parser.headers
# readings 
parser.readings
# to insert the data in the database, If same filename is loaded, function is rolled back
parser.db_insert()


from SMRT import View, File, Reading
query = View(File)
query.to_dataframe()
# Question 1 1.How many meters are in the dataset?
query = View(Reading)
query.to_dataframe('meterid').shape
# Question 2. What is all the data for a given meter? assumption '000000004'
query.to_dataframe('meterid','000000004')
# Question 3 How many files have we recieved?
h=os.listdir(r"data/")
count=0
for i in h:
    count=count+1
print("We have recieved  "+str(count)+" Files")
# 4.What was the last file to be recieved?
os.listdir(r"data/")[-1]