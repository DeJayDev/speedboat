import React, { Component, Fragment } from 'react';

import GuildsTable from './guilds_table';
import {globalState} from '../state';

class DashboardGuildsList extends Component {
  constructor() {
    super();
    this.state = {guilds: null};
  }

  UNSAFE_componentWillMount() {
    globalState.getCurrentUser().then((user) => {
      user.getGuilds().then((guilds) => {
        this.setState({guilds});
      });
    });
  }

  render() {
    return (
      <div className='card'>
        <div className='card-header'>
          Guilds
        </div>
        <div className='card-body'>
          <GuildsTable guilds={this.state.guilds}/>
        </div>
      </div>
    );
  }
}

export default function Dashboard(props) {
	return <Fragment>
      <DashboardGuildsList />
    </Fragment>
}

