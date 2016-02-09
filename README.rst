Python module for Sinch Voice REST APIs
=======================================

Installation
------------
.. code:: bash
    
    $ pip install pysinch


Usage
------------
.. code:: python

    from pysinch import SinchAPI

    sinch_client = SinchApi( 
        <APP_KEY>, 
        <APP_SECRET>, 
        <EMAIL>, 
        <PASSWORD>, 
        <NUMBER_ADMINISTRATION_KEY>
    )

    sinch_client.get_numbers()
    #sinch_client.assign_number('+46769447017')
    #sinch_client.get_callbacks()
    #sinch_client.set_callbacks('http://google.com')
    #sinch_client.query_number('+4676944')
    #sinch_client.get_call_result('4398599d1ba84ef3bde0a82dfb61abed')
    #sinch_client.manage_call('4398599d1ba84ef3bde0a82dfb61abed', 'test', [], 'hangup')
    #sinch_client.get_available_numbers()