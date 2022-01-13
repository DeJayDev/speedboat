import React, { Component } from 'react';
import { Link } from 'react-router-dom'
import {globalState} from '../state';

function SidebarLink(props) {
  const iconClass = `fas fa-${props.icon}`;

  return (
    <li>
      <Link className='nav-link' to={props.to}>
        <i className={iconClass}></i> 
        {props.text}</Link>
    </li>
  );
}


function GuildLinks(props) {
  let links = [];

  if (props.active) {
    links.push(
      <SidebarLink icon='info' to={'/guilds/' + props.guild.id} text='Information' key='info' />
    );

    links.push(
      <SidebarLink icon='cog' to={'/guilds/' + props.guild.id + '/config'} text='Config' key='config' />
    );

    links.push(
      <SidebarLink icon='ban' to={'/guilds/' + props.guild.id + '/infractions'} text='Infractions' key='infractions' />
    );

  }
  return links;
}


class Sidebar extends Component {
  constructor() {
    super();

    this.state = {
      guilds: null,
      currentGuildID: globalState.currentGuild ? globalState.currentGuild.id : null,
      showAllGuilds: globalState.showAllGuilds,
    };

    globalState.events.on('showAllGuilds.set', (value) => this.setState({showAllGuilds: value}));

    globalState.getCurrentUser().then((user) => {
      user.getGuilds().then((guilds) => {
        this.setState({guilds});
      });
    });

    globalState.events.on('currentGuild.set', (guild) => {
      this.setState({currentGuildID: guild ? guild.id : null});
    });
  }

  render() {
    let sidebarLinks = [];

    sidebarLinks.push(
      <SidebarLink icon='tachometer-alt' to='/' text='Dashboard' key='dashboard' />
    );

    if (this.state.guilds) {
      for (let guild of Object.values(this.state.guilds)) {
        // Only show the active guild for users with a lot of them
        if (
          !this.state.showAllGuilds &&
          Object.keys(this.state.guilds).length > 10 &&
          guild.id != this.state.currentGuildID
        ) continue;
        sidebarLinks.push(<GuildLinks guild={guild} active={guild.id == this.state.currentGuildID} key={guild.id} />);
      }
    }

    return (
      <div className='sidenav'>
        {sidebarLinks}
      </div>
    );
  }
}

export default Sidebar;
