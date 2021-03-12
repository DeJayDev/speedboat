import React from 'react';
import ReactDOM from 'react-dom';
import 'react-table/react-table.css'

function init() {
	// HMR requires that this be a require()
	let App = require('./components/app').default;
	ReactDOM.render( < App / > , document.getElementById('app'));
}

init();

if (module.hot) module.hot.accept('./components/app', init);
