import {statuses} from '../../constants/enums';export default function StatusBadge({status}:{status:string}){return <span className={'status '+status}>{statuses[status]||status}</span>}
