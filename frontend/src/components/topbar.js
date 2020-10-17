import React, { Component } from 'react';
import {globalState} from '../state';
import {withRouter} from 'react-router';

class Topbar extends Component {
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
			<nav className="navbar navbar-expand bg-gray-900 topbar mb-4 static-top shadow" role="navigation">
				<div className="navbar-header">
					<a className="navbar-brand text-primary">Speedboat</a>
				</div>
        <div className="topbar-divider d-none d-sm-block"></div>
				<ul className="navbar-nav ml-auto">
					<li className="nav-item mx-1"><a onClick={this.onLogoutClicked.bind(this)}><i className="fas fa-sign-out-alt"></i></a></li>
					<li className="nav-item mx-1"><a onClick={this.onExpandClicked.bind(this)}><i className={expandIcon}></i></a></li>
				</ul>
			</nav>
    );
  }
}

export default withRouter(Topbar);
