import React from 'react';
import ReactDOM from 'react-dom';
import { BrowserRouter } from 'react-router-dom';
import 'react-table-6/react-table.css'
import AppWrapper from './components/app';

ReactDOM.render(
    <BrowserRouter>
        <AppWrapper/>
    </BrowserRouter>, document.getElementById('app'));
