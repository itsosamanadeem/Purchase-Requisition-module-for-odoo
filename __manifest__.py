{
    'name': 'Purchase Requisition',
    'summary': '',
    'author': 'Osama Nadeem',
    'sequence': '-100',
    'license': 'LGPL-3',
    'depends': ['base', 'sale', 'product','purchase','stock','hr',],
    'data': [
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        'view/purchase_requisition.xml'
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': True,
}
