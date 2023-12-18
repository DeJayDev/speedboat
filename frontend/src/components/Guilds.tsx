import { Link } from "wouter";
import useStore from "../state";
import Guild from "../types/guild";

import { FaBan, FaEdit, FaInfo } from 'react-icons/fa';
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "@tremor/react";

function GuildsTable() {
  const user = useStore((state) => state.user)
  const guilds = useStore((state) => state.user?.guilds)

  if (!guilds) {
    return <h3>Loading...</h3>;
  }

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell>ID</TableHeaderCell>
          <TableHeaderCell>Name</TableHeaderCell>
          <TableHeaderCell>Actions</TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {guilds.map((guild: Guild) => {
            return <GuildTableRow guild={guild}/>
        })}
      </TableBody>
    </Table>
  );
}

function GuildTableRow(props: { guild: Guild }) {

  return (
    <TableRow key={props.guild.id}>
      <TableCell>{props.guild.id}</TableCell>
      <TableCell>{props.guild.name}</TableCell>
      <TableCell>
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
      </TableCell>
    </TableRow>
  );
}

export default GuildsTable;
