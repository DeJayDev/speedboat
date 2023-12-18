import { Link } from "wouter";
import useStore from "../state";
import Guild from "../types/guild";

import { FaBan, FaEdit, FaInfo } from 'react-icons/fa';

function GuildsTable() {
  const user = useStore((state) => state.user)
  const guilds = useStore((state) => state.user?.guilds)

  if (!guilds) {
    return <h3>Loading...</h3>;
  }

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
          {
            guilds.map((guild: Guild) => {
              return <GuildTableRow guild={guild} key={guild.id} />
            })
          }
        </tbody>
      </table>
    </div>
  );
}

function GuildTableRow(props: { guild: Guild }) {

  return (
    <tr>
      <td>{props.guild.id}</td>
      <td>{props.guild.name}</td>
      <td>
        <div>
          <Link to={`/guilds/${props.guild.id}`}>
            <button type='button' className='btn btn-success btn-circle'>
              <FaInfo />
            </button>
          </Link>
          <Link to={`/guilds/${props.guild.id}/config`}>
            <button type='button' className='btn btn-info btn-circle'>
              <FaEdit />
            </button>
          </Link>
          <Link to={`/guilds/${props.guild.id}/infractions`}>
            <button type='button' className='btn btn-danger btn-circle'>
              <FaBan />
            </button>
          </Link>
        </div>
      </td>
    </tr>
  );
}

export default GuildsTable;
