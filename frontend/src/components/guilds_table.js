import React from 'react';
import { state, VIEWS } from '../state';
import { Link } from 'react-router-dom';
import sortBy from 'lodash/sortBy';

function GuildTableRowActions(props) {
  function onInfo(guild) {
    state.setView(VIEWS.GUILD_OVERVIEW, {
      guild: guild,
    });
  }

  function onEdit(guild) {
    state.setView(VIEWS.GUILD_CONFIG_EDIT, {
      guild: guild,
    });
  }

  return (
    <div>
      <Link to={`/guilds/${props.guild.id}`} style={{padding: '4px'}}>
        <button type='button' className='btn btn-success btn-circle'><i className='fas fa-info'></i></button>
      </Link>
      <Link to={`/guilds/${props.guild.id}/config`} style={{padding: '4px'}}>
        <button type='button' className='btn btn-info btn-circle'><i className='fas fa-edit'></i></button>
      </Link>
      <Link to={`/guilds/${props.guild.id}/infractions`} style={{padding: '4px'}}>
        <button type='button' className='btn btn-danger btn-circle'><i className='fas fa-ban'></i></button>
      </Link>
    </div>
  );
}

function GuildTableRow(props) {

  return (
    <tr>
      <td>{props.guild.id}</td>
      <td>{props.guild.name}</td>
      <td><GuildTableRowActions guild={props.guild} /></td>
    </tr>
  );

}

function GuildsTable(props) {
  if (!props.guilds) {
    return <h3>Loading...</h3>;
  }

  let guilds = sortBy(Object.values(props.guilds), (i) => i.id);

  var rows = [];
  guilds.map((guild) => {
    rows.push(<GuildTableRow guild={guild} key={guild.id} />);
  });

  return (
    <div className='table-responsive'>
      <table className='table table-sriped table-bordered'>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
  );
}

export default GuildsTable;
