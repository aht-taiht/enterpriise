# Part of Odoo. See LICENSE file for full copyright and licensing details.

# The SellerCentral application ID of Odoo S.A.
APP_ID = 'amzn1.sp.solution.1cab4d17-1dba-47d1-968f-66b10b614b01'


# The URL of the Amazon proxy.
PROXY_URL = 'https://iap-services.odoo.com/'


# The endpoints of the Amazon proxy.
PROXY_ENDPOINTS = {
    'authorization': '/amazon/v1/forward_authorization_request',  # Exchange LWA tokens
    'aws_tokens': '/amazon/v1/forward_aws_credentials_request',  # Request AWS credentials
}


# Base URLs of the API.
API_DOMAINS_MAPPING = {
    'us-east-1': 'https://sellingpartnerapi-na.amazon.com',  # SP-API specific to NA marketplaces.
    'eu-west-1': 'https://sellingpartnerapi-eu.amazon.com',  # SP-API specific to EU marketplaces.
    'us-west-2': 'https://sellingpartnerapi-fe.amazon.com',  # SP-API specific to FE marketplaces.
}

# Mapping of API operation to URL paths and restricted resource paths.
API_PATHS_MAPPING = {
    'createFeed': {
        'url_path': '/feeds/2021-06-30/feeds',
        'restricted_resource_path': None,
    },
    'createFeedDocument': {
        'url_path': '/feeds/2021-06-30/documents',
        'restricted_resource_path': None,
    },
    'createRestrictedDataToken': {
        'url_path': '/tokens/2021-03-01/restrictedDataToken',
        'restricted_resource_path': None,
    },
    'getMarketplaceParticipations': {
        'url_path': '/sellers/v1/marketplaceParticipations',
        'restricted_resource_path': None,
    },
    'getOrders': {
        'url_path': '/orders/v0/orders',
        'restricted_resource_path': None,
    },
    'getOrderAddress': {
        'url_path': '/orders/v0/orders/{param}/address',
        'restricted_resource_path': '/orders/v0/orders/{this_is_bullshit}/address',
    },
    'getOrderBuyerInfo': {
        'url_path': '/orders/v0/orders/{param}/buyerInfo',
        'restricted_resource_path': '/orders/v0/orders/{this_is_bullshit}/buyerInfo',
    },
    'getOrderItems': {
        'url_path': '/orders/v0/orders/{param}/orderItems',
        'restricted_resource_path': None,
    },
    'getOrderItemsBuyerInfo': {
        'url_path': '/orders/v0/orders/{param}/orderItems/buyerInfo',
        'restricted_resource_path': '/orders/v0/orders/{this_is_bullshit}/orderItems/buyerInfo',
    },
}


# Mapping of Amazon fulfillment channels to Amazon status to synchronize.
STATUS_TO_SYNCHRONIZE = {
    'AFN': ['Shipped'],
    'MFN': ['Unshipped'],
}


# Mapping of Amazon Carrier Names
# See https://images-na.ssl-images-amazon.com/images/G/01/rainier/help/xsd/release_4_1/amzn-base.xsd

AMAZON_CARRIER_NAMES_MAPPING = {
    'selfdelivery': 'Self Delivery',  # Specific name recognized by Amazon for "custom tracking ref"

    '4px': '4PX',
    'a1': 'A-1',
    'aaacooper': 'AAA Cooper',
    'abf': 'ABF',
    'aflfedex': 'AFL/Fedex',
    'alljoy': 'ALLJOY',
    'amauk': 'AMAUK',
    'amazonshipping': 'Amazon Shipping',
    'amzl': 'AMZL',
    'amzluk': 'AMZL_UK',
    'andere': 'Andere',
    'ao': 'AO',
    'aodeutschland': 'AO Deutschland',
    'apc': 'APC',
    'apcovernight': 'APC-Overnight',
    'aramex': 'Aramex',
    'araskargo': 'Aras Kargo',
    'arcospedizioni': 'Arco Spedizioni',
    'arkas': 'Arkas',
    'arrowxl': 'Arrow XL',
    'asendia': 'Asendia',
    'asgard': 'Asgard',
    'assett': 'Assett',
    'atpost': 'AT Post',
    'ats': 'ATS',
    'aussiepost': 'AUSSIE_POST',
    'australiapost': 'Australia Post',
    'australiapostarticleid': 'Australia Post-ArticleId',
    'australiapostconsignment': 'Australia Post-Consignment',
    'b2c': 'B2C',
    'b2ceurope': 'B2C Europe',
    'balnak': 'Balnak',
    'bartolini': 'Bartolini',
    'beijingquanfengexpress': 'Beijing Quanfeng Express',
    'bestbuy': 'Best Buy',
    'bestexpress': 'Best Express',
    'bjs': 'BJS',
    'bluedart': 'BlueDart',
    'bluepackage': 'Blue Package',
    'bombax': 'Bombax',
    'bpost': 'BPOST',
    'brt': 'BRT',
    'canadapost': 'Canada Post',
    'cargoline': 'CargoLine',
    'caribou': 'Caribou',
    'cart2india': 'Cart2India',
    'cbl': 'CBL',
    'cdc': 'CDC',
    'celeritas': 'CELERITAS',
    'centex': 'Centex',
    'ceva': 'CEVA',
    'cevalojistik': 'Ceva Lojistik',
    'chinapost': 'China Post',
    'chronoexpress': 'Chrono Express',
    'chronopost': 'Chronopost',
    'chukou1': 'Chukou1',
    'cititrans': 'Cititrans',
    'citylink': 'City Link',
    'citypost': 'Citypost',
    'cne': 'CNE',
    'coliposte': 'Coliposte',
    'colisprive': 'COLIS PRIVE',
    'colissimo': 'Colissimo',
    'consegnamezzipropri': 'Consegna Mezzi Propri',
    'conway': 'Conway',
    'correios': 'Correios',
    'correos': 'Correos',
    'correosexpress': 'Correos Express',
    'couriersplease': 'CouriersPlease',
    'cttexpress': 'CTT EXPRESS',
    'cubyn': 'Cubyn',
    'dachser': 'DACHSER',
    'dacsher': 'DACSHER',
    'dascher': 'DASCHER',
    'dbschenker': 'DB Schenker',
    'deldeliveries': 'DEL Deliveries',
    'delhivery': 'Delhivery',
    'delivengo': 'Delivengo',
    'deliverygroup': 'Delivery Group',
    'derkurier': 'Der Kurier',
    'deutschepost': 'Deutsche Post',
    'dhl': 'DHL',
    'dhlecommerce': 'DHL eCommerce',
    'dhlexpress': 'DHL Express',
    'dhlfreight': 'DHL Freight',
    'dhlglobalmail': 'DHL Global Mail',
    'dhlhomedelivery': 'DHL Home Delivery',
    'dhlkargo': 'DHL Kargo',
    'dhlpaket': 'DHL-Paket',
    'dhlpl': 'DHLPL',
    'digitaldelivery': 'Digital Delivery',
    'directlog': 'DirectLog',
    'dotzot': 'Dotzot',
    'dpb': 'DPB',
    'dpd': 'DPD',
    'dpdlocal': 'DPD Local',
    'dsv': 'DSV',
    'dtdc': 'DTDC',
    'dx': 'DX',
    'dxexpress': 'DX Express',
    'dxfreight': 'DX Freight',
    'dxsecure': 'DX Secure',
    'dynamicexpress': 'DYNAMIC EXPRESS',
    'ecms': 'ECMS',
    'ecomexpress': 'Ecom Express',
    'einsasourcing': 'EINSA SOURCING',
    'ekitrans': 'EKI Trans',
    'emiratespost': 'Emirates Post',
    'emons': 'Emons',
    'endopack': 'Endopack',
    'energo': 'Energo',
    'envialia': 'Envialia',
    'equick': 'Equick',
    'estafeta': 'Estafeta',
    'estes': 'Estes',
    'eub': 'EUB',
    'europaczka': 'Europaczka',
    'exapaq': 'Exapaq',
    'fastest': 'FAST EST',
    'fastway': 'Fastway',
    'fedex': 'FedEx',
    'fedexfreight': 'Fedex Freight',
    'fedexjp': 'FEDEX_JP',
    'fedexsmartpost': 'FedEx SmartPost',
    'fercam': 'FERCAM',
    'fillokargo': 'Fillo Kargo',
    'firstflight': 'First Flight',
    'firstflightchina': 'First Flight China',
    'firstmile': 'First Mile',
    'frachtpost': 'FRACHTPOST',
    'franceexpress': 'France Express',
    'gati': 'Gati',
    'gel': 'GEL',
    'gelexpress': 'GEL Express',
    'geodis': 'GEODIS',
    'geodiscalberson': 'Geodis Calberson',
    'geopostkargo': 'Geopost Kargo',
    'gfs': 'GFS',
    'gls': 'GLS',
    'go': 'GO!',
    'grupologistic': 'GRUPO LOGISTIC',
    'hellmann': 'Hellmann',
    'heppner': 'Heppner',
    'hermes': 'Hermes',
    'hermescorporate': 'Hermes (Corporate)',
    'hermeseinrichtungsservice': 'Hermes Einrichtungsservice',
    'hermeslogistikgruppe': 'Hermes Logistik Gruppe',
    'hermesuk': 'Hermes UK',
    'hlog': 'Hlog',
    'homelogistics': 'Home Logistics',
    'honesteye': 'honesteye',
    'hongkongpost': 'Hongkong Post',
    'horozlojistik': 'Horoz Lojistik',
    'hotpointlogistics': 'Hotpoint Logistics',
    'hrp': 'HRP',
    'hscode': 'HS code',
    'hubeurope': 'HubEurope',
    'hunterlogistics': 'Hunter Logistics',
    'huxloe': 'Huxloe',
    'huxloelogistics': 'Huxloe Logistics',
    'iccworldwide': 'ICC Worldwide',
    'ids': 'IDS',
    'idsnetzwerk': 'IDS Netzwerk',
    'imile': 'iMile',
    'indiapost': 'India Post',
    'inpost': 'InPost',
    'interlink': 'Interlink',
    'interno': 'Interno',
    'intersoft': 'Intersoft',
    'iparcel': 'iParcel',
    'itdglobal': 'ITD Global',
    'japanpost': 'Japan Post',
    'jcex': 'JCEX',
    'jerseypost': 'Jersey Post',
    'jpexpress': 'JP_EXPRESS',
    'jplupu': 'JPL UPU',
    'kargokar': 'Kargokar',
    'keavo': 'KEAVO',
    'kuehnenagel': 'Kuehne+Nagel',
    'kybotech': 'Kybotech',
    'landmark': 'Landmark',
    'landmarkglobal': 'Landmark Global',
    'laposte': 'La Poste',
    'lasership': 'Lasership',
    'liccardi': 'Liccardi',
    'mailalliance': 'Mail Alliance',
    'mainpost': 'Mainpost',
    'mbe': 'MBE',
    'metrokargo': 'Metro Kargo',
    'mezzipropri': 'Mezzi propri',
    'mhi': 'MHI',
    'milkman': 'Milkman',
    'mngkargo': 'MNG Kargo',
    'mondialrelay': 'Mondial Relay',
    'mrw': 'MRW',
    'mzzbriefdienst': 'MZZ Briefdienst',
    'nacex': 'Nacex',
    'narpostkargo': 'Narpost Kargo',
    'newgistics': 'Newgistics',
    'nexive': 'Nexive',
    'ninjavan': 'Ninjavan',
    'nipponexpress': 'NipponExpress',
    'nittsu': 'NITTSU',
    'noveo': 'NOVEO',
    'ntl': 'NTL',
    'ocsworldwide': 'OCS Worldwide',
    'olddominion': 'Old Dominion',
    'oneworldexpress': 'OneWorldExpress',
    'ontime': 'ONTIME',
    'ontrac': 'OnTrac',
    'osm': 'OSM',
    'other': 'Other',
    'otro': 'Otro',
    'overniteexpress': 'Overnite Express',
    'palletline': 'Palletline',
    'palletways': 'Palletways',
    'panther': 'Panther',
    'parcel2go': 'Parcel2go',
    'parcel2gocom': 'PARCEL2GO.COM',
    'parceldenonline': 'ParcelDenOnline',
    'parcelforce': 'Parcelforce',
    'parcelhub': 'Parcelhub',
    'parcelinklogistics': 'Parcelink Logistics',
    'parcelmonkey': 'Parcel Monkey',
    'parcelnet': 'Parcelnet',
    'parcelone': 'ParcelOne',
    'parcelstation': 'Parcel Station',
    'pdclogistics': 'PDC Logistics',
    'pilot': 'Pilot',
    'pilotfreight': 'Pilot Freight',
    'pin': 'PIN',
    'polishpost': 'Polish Post',
    'posteitaliane': 'Poste Italiane',
    'postmodern': 'Post Modern',
    'postnl': 'Post NL',
    'postnord': 'PostNord',
    'professional': 'Professional',
    'pttkargo': 'PTT Kargo',
    'purolator': 'PUROLATOR',
    'qexpress': 'QExpress',
    'qxpress': 'Qxpress',
    'raben': 'Raben',
    'rabengroup': 'Raben Group',
    'rbna': 'RBNA',
    'redur': 'REDUR',
    'rhenus': 'Rhenus',
    'rieck': 'Rieck',
    'rivigo': 'Rivigo',
    'rl': 'R+L',
    'rmlgb': 'RMLGB',
    'roadrunner': 'Roadrunner',
    'royalmail': 'ROYAL_MAIL',
    'rrdonnelley': 'RR Donnelley',
    'safexpress': 'Safexpress',
    'sagawa': 'SAGAWA',
    'sagawaexpress': 'SagawaExpress',
    'saia': 'Saia',
    'sailpost': 'Sailpost',
    'schweizerpost': 'Schweizer Post',
    'sda': 'SDA',
    'seino': 'Seino',
    'seinotransportation': 'SEINO TRANSPORTATION',
    'selemkargo': 'Selem Kargo',
    'sendcloud': 'Sendcloud',
    'sending': 'Sending',
    'sendle': 'SENDLE',
    'seur': 'Seur',
    'sevensenders': 'Seven Senders',
    'sfc': 'SFC',
    'sfexpress': 'SF Express',
    'shipdelight': 'Ship Delight',
    'shipeconomy': 'ShipEconomy',
    'shipglobal': 'ShipGlobal',
    'shipglobalus': 'Ship Global US',
    'shipmate': 'Shipmate',
    'shreemaruticourier': 'Shree Maruti Courier',
    'shreetirupaticourier': 'Shree Tirupati Courier',
    'shunfengexpress': 'Shunfeng Express',
    'singaporepost': 'Singapore Post',
    'smartmail': 'Smartmail',
    'sonstige': 'Sonstige',
    'southeasternfreightlines': 'South Eastern Freight Lines',
    'speedex': 'Speedex',
    'spoton': 'Spoton',
    'spring': 'SPRING',
    'springgds': 'Spring GDS',
    'sprint': 'Sprint',
    'stahlmannandsachs': 'Stahlmann and Sachs',
    'stampit': 'Stampit',
    'startrackarticleid': 'StarTrack-ArticleID',
    'startrackconsignment': 'StarTrack-Consignment',
    'stg': 'STG',
    'stoexpress': 'STO Express',
    'streamlite': 'Streamlite',
    'sunyou': 'Sunyou',
    'susa': 'Susa',
    'swisspost': 'Swiss post',
    'szendex': 'Szendex',
    'target': 'Target',
    'tdn': 'TDN',
    'tezellojistik': 'Tezel Lojistik',
    'thedeliverygroup': 'The Delivery Group',
    'theprofessionalcouriers': 'The Professional Couriers',
    'tipsa': 'TIPSA',
    'tnt': 'TNT',
    'tntit': 'TNTIT',
    'tntkargo': 'TNT Kargo',
    'tollglobalexpress': 'Toll Global Express',
    'totalexpress': 'Total Express',
    'tourline': 'Tourline',
    'trackon': 'Trackon',
    'trakpak': 'Trakpak',
    'transaher': 'Transaher',
    'transaragonãs': 'TransaragonÃ©s',
    'transfolha': 'TransFolha',
    'translink': 'Translink',
    'transoflex': 'Trans-o-Flex',
    'truline': 'Truline',
    'tsb': 'TSB',
    'tuffnells': 'Tuffnells',
    'tws': 'TWS',
    'txt': 'TXT',
    'tyd': 'TyD',
    'ubi': 'UBI',
    'ukmail': 'UK MAIL',
    'upakweship': 'UPakWeShip',
    'ups': 'UPS',
    'upsfreight': 'UPS Freight',
    'upsilon': 'Upsilon',
    'upsmailinnovations': 'UPS Mail Innovations',
    'upsmi': 'UPSMI',
    'urbanexpress': 'Urban Express',
    'usps': 'USPS',
    'verageshipping': 'Verage Shipping',
    'viaxpress': 'Via Xpress',
    'vir': 'VIR',
    'vnlin': 'VNLIN',
    'wanbexpress': 'WanbExpress',
    'watkinsandshepard': 'Watkins and Shepard',
    'whistl': 'Whistl',
    'whizzard': 'Whizzard',
    'winit': 'WINIT',
    'wpx': 'WPX',
    'xdp': 'XDP',
    'xpo': 'XPO',
    'xpofreight': 'XPO Freight',
    'xpressbees': 'Xpressbees',
    'yamato': 'YAMATO',
    'yamatotransport': 'YamatoTransport',
    'yanwen': 'Yanwen',
    'ydh': 'YDH',
    'yellowfreight': 'Yellow Freight',
    'yodel': 'Yodel',
    'ytoexpress': 'YTO Express',
    'yundaexpress': 'Yunda Express',
    'yunexpress': 'Yun Express',
    'zeleris': 'Zeleris',
    'ztoexpress': 'ZTO Express',
    'zustambrosetti': 'Zust Ambrosetti'
}
