import datetime as dt
import time
import enum
import logging
import urllib.parse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import io
import zipfile
import os
import shutil
import pickle

logger = logging.getLogger(__name__)


class IndexSymbol(enum.Enum):
    All = 'ALL'
    FnO = 'FNO'
    Nifty50 = 'NIFTY 50'
    NiftyNext50 = 'NIFTY NEXT 50'
    Nifty100 = 'NIFTY 100'
    Nifty200 = 'NIFTY 200'
    Nifty500 = 'NIFTY 500'
    NiftyMidcap50 = 'NIFTY MIDCAP 50'
    NiftyMidcap100 = 'NIFTY MIDCAP 100'
    NiftySmlcap100 = 'NIFTY SMLCAP 100'
    NiftyMidcap150 = 'NIFTY MIDCAP 150'
    NiftySmlcap50 = 'NIFTY SMLCAP 50'
    NiftySmlcap250 = 'NIFTY SMLCAP 250'
    NiftyMidsml400 = 'NIFTY MIDSML 400'
    NiftyBank = 'NIFTY BANK'
    NiftyAuto = 'NIFTY AUTO'
    NiftyFinService = 'NIFTY FIN SERVICE'
    NiftyFmcg = 'NIFTY FMCG'
    NiftyIt = 'NIFTY IT'
    NiftyMedia = 'NIFTY MEDIA'
    NiftyMetal = 'NIFTY METAL'
    NiftyPharma = 'NIFTY PHARMA'
    NiftyPsuBank = 'NIFTY PSU BANK'
    NiftyPvtBank = 'NIFTY PVT BANK'
    NiftyRealty = 'NIFTY REALTY'
    Nifty50Value20 = 'NIFTY50 VALUE 20'
    NiftyAlpha50 = 'NIFTY ALPHA 50'
    Nifty50EqlWgt = 'NIFTY50 EQL WGT'
    Nifty100EqlWgt = 'NIFTY100 EQL WGT'
    Nifty100Lowvol30 = 'NIFTY100 LOWVOL30'
    Nifty200Qualty30 = 'NIFTY200 QUALTY30'
    NiftyCommodities = 'NIFTY COMMODITIES'
    NiftyConsumption = 'NIFTY CONSUMPTION'
    NiftyEnergy = 'NIFTY ENERGY'
    NiftyInfra = 'NIFTY INFRA'
    NiftyMnc = 'NIFTY MNC'
    NiftyPse = 'NIFTY PSE'
    NiftyServSector = 'NIFTY SERV SECTOR'


class OutputType(enum.Enum):
    pandas = 'pd'
    dict = 'json'


class Format(enum.Enum):
    pkl = 'pkl'
    csv = 'csv'


class Segment(enum.Enum):
    EQ = 'EQ'
    FUT = 'FUT'
    OPT = 'OPT'


class OptionType(enum.Enum):
    CE = 'Call'
    PE = 'Put'


class MostActive(enum.Enum):
    AllFnO = 'contracts&limit=10'
    EQ = ''
    Options = 'options'
    Futures = 'futures'
    Calls = 'calls'
    Puts = 'puts'
    OI = 'oi'


class Nse:
    """
    pynse is a library to extract realtime and historical data from NSE website

    Examples
    --------

    >>> from pynse import *
    >>> nse = Nse()
    >>> nse.market_status()

    """

    def __init__(self, path:str='data'):
        self.expiry_list = list()
        self.strike_list = list()
        self.max_retries = 5
        self.timeout = 10
        self.__urls, self.__wrls = dict(), list()
        self.data_root = {'data_root': path}
        self.data_root.update({d: f'{self.data_root["data_root"]}/{d}/' for d in
                               ['bhavcopy_eq', 'bhavcopy_fno', 'option_chain', 'symbol_list', 'pre_open', 'hist',
                                'fii_dii', 'config', 'eq_stock_watch', 'daily_delivery', 'insider_trading',
                                'corp_info', 'screen_shots']})
        self.__symbol_files = {i.name: f"{self.data_root['symbol_list']}{i.name}.pkl" for i in IndexSymbol}
        self.__zero_files = {i.name: f"{f'{os.path.split(__file__)[0]}/symbol_list/'}{i.name}.pkl" for i in IndexSymbol}
        self.__startup()
        self.__headers = self.__desc(new=False)
        self.symbols = {i.name: self.__read_object(self.__symbol_files[i.name], Format.pkl) for i in IndexSymbol}

    def __get_resp(self, url, retries=0, timeout=0):
        retries = self.max_retries if retries == 0 else retries
        timeout = self.timeout if timeout == 0 else timeout
        self.__headers.update({'Referer': np.random.choice(self.__wrls)})

        for nrt in range(retries):
            try:
                time.sleep(5)
                # response = requests.get(url, headers=self.__headers, timeout=timeout)
                
                # Fix for new NSE session issue
                session = requests.Session()
                response = session.get("http://nseindia.com", headers=self.__headers)
                response = session.get(url, headers=self.__headers, timeout=timeout)
            except Exception as e:
                logger.error(e)
                if nrt + 1 == retries:
                    try:
                        if requests.get(url='https://www.google.com/', headers=self.__headers,
                                        timeout=timeout).status_code == 200:
                            logging.error('Try slowing down\n'
                                          'or try after sometime')
                    except:
                        logging.error('cannot connect to internet')
                    raise ConnectionError()
                self.__desc()
                logger.debug('retrying')
                time.sleep(10)
            else:
                return response

    def __desc(self, new=True):
        from fake_headers import Headers
        hfile = f'{self.data_root["config"]}hf'
        if new or not os.path.exists(hfile):
            h = Headers(headers=True).generate()
            with open(hfile, 'wb') as f:
                pickle.dump(h, f)
        else:
            with open(hfile, 'rb') as f:
                h = pickle.load(f)
        return h

    def __startup(self):
        for _, path in self.data_root.items():
            if path != '':
                if not os.path.exists(path):
                    os.mkdir(path)

        if not os.path.exists(self.__symbol_files['All']):
            logger.debug('First run.\nCreating folders and symbol files')
            for i in IndexSymbol:
                if not os.path.exists(self.__symbol_files[i.name]):
                    try:
                        shutil.copyfile(self.__zero_files[i.name], self.__symbol_files[i.name])
                    except Exception as e:
                        logger.error(e)
        self.__urls, self.__wrls = self.__read_object(f'{os.path.split(__file__)[0]}/symbol_list/config', Format.pkl)

    @staticmethod
    def __read_object(filename, format):
        if format == Format.pkl:
            with open(filename, 'rb')as f:
                obj = pickle.load(f)
            return obj
        elif format == Format.csv:
            with open(filename, 'r')as f:
                obj = f.read()
            return obj
        else:
            raise FileNotFoundError(f'{filename} not found')

    @staticmethod
    def __save_object(obj, filename, format):
        if format == Format.pkl:
            with open(filename, 'wb')as f:
                pickle.dump(obj, f)
        elif format == Format.csv:
            with open(filename, 'w')as f:
                f.write(obj)
        logger.debug(f'saved {filename}')

    @staticmethod
    def __validate_symbol(symbol, _list):
        symbol = symbol if isinstance(symbol, IndexSymbol) else symbol.upper()
        if isinstance(symbol, IndexSymbol):
            symbol = urllib.parse.quote(symbol.value)
            return symbol
        elif symbol in _list:
            symbol = urllib.parse.quote(symbol.upper())
            return symbol
        else:
            symbol = None
            raise ValueError('not a vaild symbol')

    def market_status(self) -> dict:
        """
        get market status

        Examples
        --------

        >>> nse.market_status()

        """
        config = self.__urls
        logger.info("downloading market status")
        url = config['host'] + config['path']['marketStatus']
        return self.__get_resp(url=url).json()

    def info(self, symbol: str = 'SBIN') -> dict:
        '''
        Get symbol information from nse

        Examples
        --------

        >>> nse.info('SBIN')

        '''
        config = self.__urls
        symbol = self.__validate_symbol(symbol, self.symbols[IndexSymbol.All.name])
        if symbol is not None:
            logger.info(f"downloading symbol info for {symbol}")
            url = config['host'] + config['path']['info'].format(symbol=symbol)
            return self.__get_resp(url=url).json()

    def get_quote(self,
                  symbol: str = 'HDFC',
                  segment: Segment = Segment.EQ,
                  expiry: dt.date = None,
                  optionType: OptionType = OptionType.CE,
                  strike: str = '-') -> dict:
        """

        Get realtime quote for EQ, FUT and OPT

        if no expiry date is provided for derivatives, returns date for nearest expiry

        Examples
        --------
        for cash
        >>> nse.get_quote('RELIANCE')

        for futures
        >>> nse.get_quote('TCS', segment=Segment.FUT, expiry=dt.date( 2020, 6, 30 ))

        for options
        >>> nse.get_quote('HDFC', segment=Segment.OPT, optionType=OptionType.PE)

        """
        config = self.__urls
        segment = segment.value
        optionType = optionType.value

        if symbol is not None:
            logger.info(f"downloading quote for {symbol} {segment}")
            quote = {}
            if segment == 'EQ':
                symbol = self.__validate_symbol(symbol,
                                                self.symbols[IndexSymbol.All.name] + [idx.value for idx in IndexSymbol])
                url = config['host'] + config['path']['quote_eq'].format(symbol=symbol)
                url1 = config['host'] + config['path']['trade_info'].format(symbol=symbol)
                data = self.__get_resp(url).json()
                data.update(self.__get_resp(url1).json())
                quote = data['priceInfo']
                quote['timestamp'] = dt.datetime.strptime(data['metadata']['lastUpdateTime'], '%d-%b-%Y %H:%M:%S')
                quote.update(series=data['metadata']['series'])
                quote.update(symbol=data['metadata']['symbol'])
                quote.update(data['securityWiseDP'])
                quote['low'] = quote['intraDayHighLow']['min']
                quote['high'] = quote['intraDayHighLow']['max']

            elif segment == 'FUT':
                symbol = self.__validate_symbol(symbol,
                                                self.symbols[IndexSymbol.FnO.name] + ['NIFTY', 'BANKNIFTY'])
                url = config['host'] + config['path']['quote_derivative'].format(symbol=symbol)
                data = self.__get_resp(url).json()
                quote['timestamp'] = dt.datetime.strptime(data['fut_timestamp'], '%d-%b-%Y %H:%M:%S')
                data = [
                    i for i in data['stocks']
                    if segment.lower() in i['metadata']['instrumentType'].lower()
                ]
                expiry_list = list(
                    dict.fromkeys([dt.datetime.strptime(i['metadata']['expiryDate'], '%d-%b-%Y').date() for i in data]))
                if expiry is None:
                    expiry = expiry_list[0]
                data = [i for i in data if
                        dt.datetime.strptime(i['metadata']['expiryDate'], '%d-%b-%Y').date() == expiry]
                quote.update(data[0]['marketDeptOrderBook']['tradeInfo'])
                quote.update(data[0]['metadata'])
                quote['expiryDate'] = dt.datetime.strptime(quote['expiryDate'], '%d-%b-%Y').date()

            elif segment == 'OPT':
                url = config['host'] + config['path']['quote_derivative'].format(symbol=symbol)
                data = self.__get_resp(url).json()
                quote['timestamp'] = dt.datetime.strptime(data['opt_timestamp'], '%d-%b-%Y %H:%M:%S')
                data = [
                    i for i in data['stocks']
                    if segment.lower() in i['metadata']['instrumentType'].lower()
                       and i['metadata']['optionType'] == optionType
                ]
                self.strike_list = list(dict.fromkeys(
                    [i['metadata']['strikePrice'] for i in data]))
                strike = strike if strike in self.strike_list else self.strike_list[0]
                self.expiry_list = list(
                    dict.fromkeys([dt.datetime.strptime(i['metadata']['expiryDate'], '%d-%b-%Y').date() for i in data]))

                if expiry is None:
                    expiry = self.expiry_list[0]
                data = [i for i in data if
                        dt.datetime.strptime(i['metadata']['expiryDate'], '%d-%b-%Y').date() == expiry and
                        i['metadata']['strikePrice'] == strike]
                quote.update(data[0]['marketDeptOrderBook']['tradeInfo'])
                quote.update(data[0]['marketDeptOrderBook']['otherInfo'])
                quote.update(data[0]['metadata'])
                quote['expiryDate'] = dt.datetime.strptime(quote['expiryDate'], '%d-%b-%Y').date()

            return quote

    def bhavcopy(self, req_date: dt.date = None,
                 series: str = 'eq') -> pd.DataFrame:
        """
        download bhavcopy from nse
        or
        read bhavcopy if already downloaded

        Examples
        --------

        >>> nse.bhavcopy()

        >>> nse.bhavcopy(dt.date(2020,6,17))
        """

        series = series.upper()
        req_date = self.__trading_days()[-1].date() if req_date is None else req_date
        filename = f'{self.data_root["bhavcopy_eq"]}bhav_{req_date}.pkl'
        bhavcopy = None
        if os.path.exists(filename):
            bhavcopy = pd.read_pickle(filename)
            logger.debug(f'read {filename} from disk')
        else:
            config = self.__urls
            url = config['path']['bhavcopy'].format(date=req_date.strftime("%d%m%Y"))
            csv = self.__get_resp(url).content.decode('utf8').replace(" ", "")
            bhavcopy = pd.read_csv(io.StringIO(csv))
            bhavcopy["DATE1"] = bhavcopy["DATE1"].apply(lambda x: dt.datetime.strptime(x, '%d-%b-%Y').date())
            bhavcopy.to_pickle(filename)

        if bhavcopy is not None:
            if series != 'ALL':
                bhavcopy = bhavcopy.loc[bhavcopy['SERIES'] == series]
            bhavcopy.set_index(['SYMBOL', 'SERIES'], inplace=True)

        return bhavcopy

    def bhavcopy_fno(self, req_date: dt.date = None) -> pd.DataFrame:
        """
        download bhavcopy from nse
        or
        read bhavcopy if already downloaded

        Examples
        --------

        >>> nse.bhavcopy_fno()

        >>> nse.bhavcopy_fno(dt.date(2020,6,17))

        """
        req_date = self.__trading_days()[-1].date() if req_date is None else req_date
        filename = f'{self.data_root["bhavcopy_fno"]}bhav_{req_date}.pkl'
        bhavcopy = None
        if os.path.exists(filename):
            bhavcopy = pd.read_pickle(filename)
            logger.debug(f'read {filename} from disk')
        else:
            config = self.__urls
            url = config['path']['bhavcopy_derivatives'].format(date=req_date.strftime("%d%b%Y").upper(),
                                                                month=req_date.strftime("%b").upper(),
                                                                year=req_date.strftime("%Y"))
            logger.debug("downloading bhavcopy for {}".format(req_date))
            stream = self.__get_resp(
                url).content
            filebytes = io.BytesIO(stream)
            zf = zipfile.ZipFile(filebytes)
            bhavcopy = pd.read_csv(zf.open(zf.namelist()[0]))
            bhavcopy.set_index('SYMBOL', inplace=True)
            bhavcopy.dropna(axis=1, inplace=True)
            bhavcopy.EXPIRY_DT = bhavcopy.EXPIRY_DT.apply(lambda x: dt.datetime.strptime(x, '%d-%b-%Y'))
            bhavcopy.to_pickle(filename)

        return bhavcopy

    def pre_open(self) -> pd.DataFrame:
        """

        get pre open data from nse

        Examples
        --------

        >>> nse.pre_open()

        """

        filename = f"{self.data_root['pre_open']}{dt.date.today()}.pkl"
        if os.path.exists(filename):
            pre_open_data = pd.read_pickle(filename)
            logging.debug('pre_open data read from file')

        else:
            logger.debug("downloading preopen data")
            config = self.__urls
            url = config['host'] + config['path']['preOpen']
            data = self.__get_resp(url).json()
            timestamp = dt.datetime.strptime(data['timestamp'], "%d-%b-%Y %H:%M:%S").date()
            pre_open_data = pd.json_normalize(data['data'])
            pre_open_data = pre_open_data.set_index('metadata.symbol')
            pre_open_data["detail.preOpenMarket.lastUpdateTime"] = pre_open_data[
                "detail.preOpenMarket.lastUpdateTime"].apply(
                lambda x: dt.datetime.strptime(x, '%d-%b-%Y %H:%M:%S'))
            filename = f"{self.data_root['pre_open']}{timestamp}.pkl"
            pre_open_data.to_pickle(filename)

        return pre_open_data

    def __option_chain_download(self, symbol):
        symbol = self.__validate_symbol(symbol, self.symbols[IndexSymbol.FnO.name] + ['NIFTY', 'BANKNIFTY', 'NIFTYIT'])
        logger.debug('download option chain')
        config = self.__urls
        url = config['host'] + (config['path']['option_chain_index'] if 'NIFTY' in symbol else config['path'][
            'option_cahin_equities']).format(symbol=symbol)
        data = self.__get_resp(url).json()
        return data

    def option_chain(self, symbol: str = 'NIFTY', req_date: dt.date = None) -> dict:
        """
        downloads the option chain
        or
        reads if already downloaded

        if no req_date is specified latest available option chain from nse website

        :returns dictonaly containing
            timestamp as str
            option chain as pd.Dataframe
            expiry_list as list

        Examples
        --------

        >>> nse.option_chain('INFY')

        >>> nse.option_chain('INFY',expiry=dt.date(2020,6,30))

        """
        dir = f"{self.data_root['option_chain']}{symbol}/"
        if not os.path.exists(dir):
            os.mkdir(dir)

        download_req = True
        filename = f"{dir}{dt.date.today()}_eod.pkl"

        if os.path.exists(filename):
            download_req = False
        elif req_date is None:

            q = self.get_quote(np.random.choice(self.symbols['FnO']))
            logger.debug('got timestamp')
            timestamp = q['timestamp'] if q is not None else None
            if timestamp.date() == dt.date.today() and timestamp.time() <= dt.time(15, 30):
                filename = f"{dir}{dt.date.today()}_{dt.datetime.now().strftime('%H%M%S')}.pkl"
                download_req = True
            elif timestamp.date() == dt.date.today():
                filename = f"{dir}{dt.date.today()}_eod.pkl"
                download_req = False if os.path.exists(filename) else True
            else:
                prev_trading_day = self.__trading_days()[-1].date()
                filename = f"{dir}{prev_trading_day}_eod.pkl"
                download_req = False if os.path.exists(filename) else True
        else:
            if req_date == dt.date.today():
                q = self.get_quote()
                timestamp = dt.datetime.strptime(self.get_quote()['timestamp'],
                                                 "%d-%b-%Y %H:%M:%S") if q is not None else None
                if timestamp.date() == dt.date.today() and timestamp.time() <= dt.time(15, 30):
                    filename = f"{dir}{req_date}_{dt.datetime.now().strftime('%H%M%S')}.pkl"
                    download_req = True
                else:
                    filename = filename = f"{dir}{req_date}_eod.pkl"
                    download_req = False if os.path.exists(filename) else True
            else:
                prev_trading_day = self.__trading_days()[-1]
                if req_date >= prev_trading_day:
                    filename = filename = f"{dir}{prev_trading_day}_eod.pkl"
                    download_req = False if os.path.exists(filename) else True
                else:
                    filename = filename = f"{dir}{req_date}_eod.pkl"
                    download_req = False
        if download_req:
            data = self.__option_chain_download(symbol)
            self.__save_object(data, filename, Format.pkl)
        data = self.__read_object(filename, Format.pkl)
        expiry_list = data['records']['expiryDates']
        option_chain = pd.json_normalize(data['records']['data'])
        timestamp = data['records']['timestamp']
        return {'timestamp': timestamp, 'data': option_chain, 'expiry_list': expiry_list}

    def fii_dii(self) -> pd.DataFrame:
        """
        get FII and DII data from nse

        Examples
        --------

        >>> nse.fii_dii()

        """

        filename = f'{self.data_root["fii_dii"]}fii_dii.csv'

        if not os.path.exists(filename):
            mode = 'w'
            timestamp = dt.date.today() - dt.timedelta(days=2)
        else:
            mode = 'a'
            csv_file = pd.read_csv(filename, header=[0, 1], index_col=[0])
            timestamp = dt.datetime.strptime(csv_file.tail(1).index[0], '%d-%b-%Y').date()
        if timestamp == dt.date.today() or timestamp == dt.date.today() - dt.timedelta(
                days=1) and dt.datetime.now().time() < dt.time(15, 30):
            logger.debug('read fii/dii data from disk')
            return csv_file.tail(1)
        else:
            config = self.__urls
            url = config['host'] + config['path']['fii_dii']
            resp = self.__get_resp(url).json()
            resp[0].pop('date')
            date = resp[1].pop('date')
            fii = [d for d in resp if d['category'] == 'FII/FPI *'][0]
            dii = [d for d in resp if d['category'] == 'DII **'][0]
            fii_dii = pd.concat(
                [pd.json_normalize(fii),
                 pd.json_normalize(dii)],
                axis=1,
                keys=[fii['category'], dii['category']])
            fii_dii.index = [date]
            if dt.datetime.strptime(date, '%d-%b-%Y').date() != timestamp:
                fii_dii.to_csv(filename, mode=mode, header=True if mode == 'w' else False)
            return fii_dii.tail(1)

    def __get_hist(self, symbol='SBIN', from_date=None, to_date=None):
        config = self.__urls
        max_date_range = 480
        if from_date == None:
            from_date = dt.date.today() - dt.timedelta(days=30)
        if to_date == None:
            to_date = dt.date.today()
        hist = pd.DataFrame()
        while True:
            if (to_date - from_date).days > max_date_range:
                marker = from_date + dt.timedelta(max_date_range)
                url = config['host'] + config['path']['hist'].format(symbol=symbol,
                                                                     from_date=from_date.strftime('%d-%m-%Y'),
                                                                     to_date=marker.strftime('%d-%m-%Y'))
                from_date = from_date + dt.timedelta(days=(max_date_range + 1))
                csv = self.__get_resp(url).content.decode('utf8').replace(" ", "")
                is_complete = False
            else:
                url = config['host'] + config['path']['hist'].format(symbol=symbol,
                                                                     from_date=from_date.strftime('%d-%m-%Y'),
                                                                     to_date=to_date.strftime('%d-%m-%Y'))
                from_date = from_date + dt.timedelta(max_date_range + 1)
                csv = self.__get_resp(url).content.decode('utf8').replace(" ", "")
                is_complete = True
            hist = pd.concat([hist, pd.read_csv(io.StringIO(csv))[::-1]])
            if is_complete:
                break
            time.sleep(1)
        hist['Date'] = pd.to_datetime(hist['Date'])
        hist.set_index('Date', inplace=True)
        hist.drop(['series', 'PREV.CLOSE', 'ltp', 'vwap', '52WH', '52WL', 'VALUE', 'Nooftrades'], axis=1, inplace=True)
        try:
            hist.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        except Exception as e:
            print(hist.columns, e)
            time.sleep(5)
        for column in hist.columns[:4]:
            hist[column] = hist[column].astype(str).str.replace(',', '').replace('-', '0').astype(float)
        hist['Volume'] = hist['Volume'].astype(int)
        return hist

    def __get_hist_index(self, symbol='NIFTY 50', from_date=None,
                         to_date=None):
        if from_date == None:
            from_date = dt.date.today() - dt.timedelta(days=30)
        if to_date == None:
            to_date = dt.date.today()
        config = self.__urls
        base_url = config['path']['indices_hist_base']
        urls = []
        max_range_len = 100
        while True:
            if (to_date - from_date).days > max_range_len:
                s = from_date
                e = s + dt.timedelta(max_range_len)
                url = f"{base_url}{symbol}&fromDate={s.strftime('%d-%m-%Y')}&toDate={e.strftime('%d-%m-%Y')}"
                urls.append(url)
                from_date = from_date + dt.timedelta(max_range_len + 1)
            else:
                url = f"{base_url}{symbol}&fromDate={from_date.strftime('%d-%m-%Y')}&toDate={to_date.strftime('%d-%m-%Y')}"
                urls.append(url)
                break
        hist = pd.DataFrame(columns=[
            'Date', 'Open', 'High', 'Low', 'Close', 'SharesTraded',
            'Turnover(Cr)'
        ])
        for url in urls:
            page = self.__get_resp(url).content.decode('utf-8')
            raw_table = BeautifulSoup(page, 'lxml').find_all('table')[0]
            rows = raw_table.find_all('tr')
            for row_no, row in enumerate(rows):
                if row_no > 2:
                    _row = [
                        cell.get_text().replace(" ", "").replace(",", "")
                        for cell in row.find_all('td')
                    ]
                    if len(_row) > 4:
                        hist.loc[len(hist)] = _row
            time.sleep(1)
        hist.Date = hist.Date.apply(lambda d: dt.datetime.strptime(d, '%d-%b-%Y'))
        hist.set_index("Date", inplace=True)
        for col in hist.columns:
            hist[col] = hist[col].astype(str).replace(',', '').replace('-', '0').astype(float)
        return hist

    def get_hist(self, symbol: str = 'SBIN', from_date: dt.date = None, to_date: dt.date = None) -> pd.DataFrame:
        """
        get historical data from nse
        symbol index or symbol

        Examples
        --------

        >>> nse.get_hist('SBIN')

        >>> nse.get_hist('NIFTY 50', from_date=dt.date(2020,1,1),to_date=dt.date(2020,6,26))

        """
        symbol = self.__validate_symbol(symbol,
                                        self.symbols[IndexSymbol.All.name] + [idx.value for idx in IndexSymbol])
        if "NIFTY" in symbol:
            return self.__get_hist_index(symbol, from_date, to_date)
        else:
            return self.__get_hist(symbol, from_date, to_date)

    def get_indices(self, index: IndexSymbol = None) -> pd.DataFrame:
        """
        get realtime index value

        Examples
        --------

        >>> nse.get_indices(IndexSymbol.NiftyInfra)
        >>> nse.get_indices(IndexSymbol.Nifty50))

        """
        if index is not None:
            self.__validate_symbol(index, [idx for idx in IndexSymbol])
        config = self.__urls
        url = config['host'] + config['path']['indices']
        data = self.__get_resp(url).json()['data']
        data = pd.json_normalize(data).set_index('indexSymbol')
        if index is not None:
            data = data[data.index == index.value]
        data.drop(['chart365dPath', 'chartTodayPath', 'chart30dPath'], inplace=True, axis=1)
        return data

    def __gainers_losers(self, index, advance=False):
        index = self.__validate_symbol(index.value, [idx.value for idx in IndexSymbol if idx.value != 'ALL'])
        index = 'SECURITIES%20IN%20F%26O' if index == 'FNO' else index
        config = self.__urls
        url = config['host'] + config['path']['gainer_loser'].format(index=index)
        data = self.__get_resp(url).json()
        if advance:
            return data["advance"]
        table = pd.DataFrame(data['data'])
        table.drop([
            'chart30dPath', 'chart365dPath', 'chartTodayPath', 'meta',
            'identifier'
        ],
            axis=1,
            inplace=True)
        table.set_index('symbol', inplace=True)
        return table

    def __symbol_list(self, index: IndexSymbol):
        """

        :param index: index name or fno
        :return: list ig symbols for selected group
        """
        if not isinstance(index, IndexSymbol):
            raise TypeError('index is not of type "Index"')
        config = self.__urls
        if index == IndexSymbol.All:
            data = list(self.bhavcopy().reset_index().SYMBOL)
        elif index == IndexSymbol.FnO:
            url = config['host'] + config['path']['fnoSymbols']
            data = self.__get_resp(url).json()
            data.extend(['NIFTY', 'BANKNIFTY'])
        else:
            url = config['host'] + config['path']['symbol_list'].format(
                index=self.__validate_symbol(index, IndexSymbol))
            data = self.__get_resp(url).json()['data']
            data = [i['meta']['symbol'] for i in data if i['identifier'] != index.value]
        data.sort()
        with open(self.data_root['symbol_list'] + index.name + '.pkl', 'wb')as f:
            pickle.dump(data, f)
            logger.info(f'symbol list saved for {index}')
        return data

    def update_symbol_list(self):
        """
        Update list of symbols
        no need to run frequently
        required when constituent of an index is changed
        or
        list of securities in fno are updates
        :return: None

        Examples:
        ```
        nse.update_symbol_list()
        ```
        """
        for i in [a for a in IndexSymbol]:
            self.__symbol_list(i)
            time.sleep(1)

    def __trading_days(self):
        filename = f'{self.data_root["data_root"]}/trading_days.csv'
        if os.path.exists(filename):
            trading_days = pd.read_csv(filename, header=None)
            trading_days.columns = ['Date']
            trading_days['Date'] = trading_days['Date'].apply(lambda x: dt.datetime.strptime(x, '%Y-%m-%d'))
            previous_trading_day = list(trading_days.tail(1)['Date'])[0].date()
        else:
            previous_trading_day = dt.date.today() - dt.timedelta(days=100)
            trading_days = pd.DataFrame()
        if previous_trading_day == dt.date.today() or previous_trading_day == dt.date.today() - dt.timedelta(
                days=1) and dt.datetime.now().time() <= dt.time(18, 45):
            pass
        else:
            _trading_days = self.get_hist(symbol='SBIN', from_date=previous_trading_day - dt.timedelta(7),
                                          to_date=dt.date.today()).reset_index()[['Date']]

            trading_days = pd.concat([trading_days, _trading_days]).drop_duplicates()
            trading_days.to_csv(filename, mode='w', index=False, header=False)
        trading_days = pd.read_csv(filename, header=None, index_col=0)
        trading_days.index = trading_days.index.map(lambda x: dt.datetime.strptime(x, "%Y-%m-%d"))
        return trading_days.index

    def top_gainers(self, index: IndexSymbol = IndexSymbol.FnO, length: int = 10) -> pd.DataFrame:
        """
        get top gainers in given index
        Examples
        --------

        >>> nse.top_gainers(IndexSymbol.FnO,length=10)

        """
        gainers = self.__gainers_losers(index).sort_values(by=['pChange'],
                                                           axis=0,
                                                           ascending=False).head(length)
        gainers = gainers[gainers.pChange > 0.]
        return gainers

    def top_losers(self, index: IndexSymbol = IndexSymbol.FnO, length: int = 10) -> pd.DataFrame:
        """
        get lop losers in given index
        Examples
        --------

        >>> nse.top_gainers(IndexSymbol.FnO,length=10)

        """
        losers = self.__gainers_losers(index).sort_values(by=['pChange'],
                                                          axis=0,
                                                          ascending=True).head(length)
        losers = losers[losers.pChange < 0.]

        return losers

    def eq_stock_watch(self) -> pd.DataFrame:
        """
        download Equity Stock Watch from nse
        or
        read eq_stock_watch if already downloaded

        Examples
        --------

        >>> nse.eq_stock_watch()

        """
        req_date = self.__trading_days()[-1].date()
        filename = f'{self.data_root["eq_stock_watch"]}eq_stock_watch_{req_date}.pkl'
        eq_stock_watch = None
        if os.path.exists(filename):
            eq_stock_watch = pd.read_pickle(filename)
            logger.debug(f'read {filename} from disk')
        else:
            config = self.__urls
            url = config['host'] + config['path']['equity_stock_watch']
            csv = self.__get_resp(url).content.decode('utf8').replace(" ", "")
            eq_stock_watch = pd.read_csv(io.StringIO(csv))
            eq_stock_watch.columns = list(map((lambda x: x.replace('\n',' ').strip()), eq_stock_watch.columns))
            logger.debug("downloading eq_stock_watch for {}".format(req_date))
            eq_stock_watch.set_index('SYMBOL', inplace=True)
            eq_stock_watch.dropna(axis=1, inplace=True)
            eq_stock_watch.to_pickle(filename)

        return eq_stock_watch

    def daily_delivery(self, req_date: dt.date = None) -> pd.DataFrame:
        """
        download Daily delivery from nse
        or
        read daily_delivery if already downloaded

        Examples
        --------

        >>> nse.daily_delivery()

        >>> nse.daily_delivery(dt.date(2020,7,20))

        """
        req_date = self.__trading_days()[-1].date() if req_date is None else req_date
        filename = f'{self.data_root["daily_delivery"]}daily_delivery_{req_date}.pkl'
        daily_delivery = None
        if os.path.exists(filename):
            daily_delivery = pd.read_pickle(filename)
            logger.debug(f'read {filename} from disk')
        else:
            config = self.__urls
            url = config['path']['daily_delivery'].format(date=req_date.strftime("%d%m%Y").upper())
            csv = self.__get_resp(url).content.decode('utf8').replace(" ", "")
            daily_delivery = pd.read_csv(io.StringIO(csv), skiprows=3, index_col=False)
            daily_delivery.columns = list(map((lambda x: x.strip()), daily_delivery.columns))
            daily_delivery.rename(columns={'NameofSecurity':'SYMBOL'}, inplace=True)
            logger.debug("downloading daily_delivery for {}".format(req_date))
            daily_delivery.set_index('SYMBOL', inplace=True)
            daily_delivery.dropna(axis=1, inplace=True)
            daily_delivery.to_pickle(filename)

        return daily_delivery

    def insider_trading(self, from_date=None, to_date=None) -> pd.DataFrame:
        """
        download Insider trading from nse
        or
        read insider_trading if already downloaded

        Examples
        --------
        >>> nse.insider_trading()
        >>> nse.insider_trading(to_date=dt.date(2020, 8, 3)
        """
        config = self.__urls
        if from_date == None:
            from_date = dt.date.today() - dt.timedelta(days=100)
        if to_date == None:
            to_date = dt.date.today()

        filename = f'{self.data_root["insider_trading"]}insider_trading_{from_date}_to_{to_date}.pkl'
        insider_trading = None
        if os.path.exists(filename):
            insider_trading = pd.read_pickle(filename)
            logger.debug(f'read {filename} from disk')
        else:
            insider_trading = pd.DataFrame()
            url = config['host'] + config['path']['insider_trading'].format(from_date=from_date.strftime('%d-%m-%Y'),
                                                                 to_date=to_date.strftime('%d-%m-%Y'))
            data = self.__get_resp(url).json()
            insider_trading = pd.DataFrame(data['data'])
            insider_trading.drop(['xbrl', 'tkdAcqm', 'anex', 'derivativeType', 'remarks'], axis=1, inplace=True)
            insider_trading.to_pickle(filename)
        return insider_trading

    def corp_info(self, symbol: str = 'SBIN', month=None, use_pickle=True):
        """
        download Corporation Info from nse
        or
        read corp_info if already downloaded

        Examples
        --------
        >>> nse.corp_info()
        >>> nse.corp_info(symbol='SBIN', month=dt.date.today().strftime('%B'))
        >>> nse.corp_info(symbol='SBIN', use_pickle=False) #Use on prod

        """
        config = self.__urls
        corp_info = {}
        if month == None:
            month = dt.date.today().strftime('%B')
        if symbol is not None:
            filename = f'{self.data_root["corp_info"]}corp_info_{symbol}_{month}.pkl'
            if use_pickle and os.path.exists(filename):
                with open(filename, 'rb') as pk:
                    corp_info = pickle.load(pk)
                logger.debug(f'read {filename} from disk')
            else:
                logger.info(f"downloading corp data for {symbol}")
                symbol = self.__validate_symbol(symbol,
                                                self.symbols[IndexSymbol.All.name] + [idx.value for idx in IndexSymbol])
                url = config['host'] + config['path']['corp_info'].format(symbol=symbol)
                data = self.__get_resp(url).json()
                corp_info['share_holding_patterns'] = pd.DataFrame(data['corporate']['shareholdingPatterns']['data'])
                corp_info['financial_results'] = pd.DataFrame(data['corporate']['financialResults'])
                corp_info['pledge_details'] = pd.DataFrame(data['corporate']['pledgedetails'])
                corp_info['sast_Regulations_29'] = pd.DataFrame(data['corporate']['sastRegulations_29'])
                if use_pickle:
                    with open(filename, 'wb') as pk:
                        pickle.dump(corp_info, pk, protocol=pickle.HIGHEST_PROTOCOL)
        return corp_info
