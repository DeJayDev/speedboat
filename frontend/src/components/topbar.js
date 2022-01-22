import React, { Component } from 'react';
import {globalState} from '../state';

export default class Topbar extends Component {
  constructor() {
    super();
    this.state = {
      showAllGuilds: globalState.showAllGuilds,
    };

    globalState.events.on('showAllGuilds.set', (value) => this.setState({showAllGuilds: value}));
  }

  onLogoutClicked() {
    globalState.logout().then(() => {
      this.props.history.push('/login');
    });
  }

  onExpandClicked() {
    globalState.showAllGuilds = !globalState.showAllGuilds;
  }

  render() {
    const expandIcon = this.state.showAllGuilds ? 'far fa-folder-open' : 'far fa-folder';

		return(
			<nav className='navbar navbar-expand-lg navbar-dark bg-primary' role='navigation'>
				<a className='navbar-brand'>Speedboat</a>
        <button className='navbar-toggler' type='button' data-toggle='collapse' data-target='#navbarSupportedContent' aria-controls='navbarSupportedContent' aria-expanded='false' aria-label='Toggle navigation'>
          <span className='navbar-toggler-icon'></span>
        </button>

        <div className='collapse navbar-collapse' id='navbarSupportedContent'>
				  <ul className='navbar-nav ml-auto'>
				  	<li className='nav-item mx-1'><a onClick={this.onLogoutClicked.bind(this)}><i className='fas fa-sign-out-alt'></i></a></li>
				  	<li className='nav-item mx-1'><a onClick={this.onExpandClicked.bind(this)}><i className={expandIcon}></i></a></li>
				  </ul>
        </div>
			</nav>
    );
  }
}

// Topbar;
//        <div className='topbar-divider d-none d-sm-block'></div>