import {request} from './client';import type {Observation} from '../types/domain';export const getObservations=(id:number)=>request<Observation[]>('/observations?benchmark_id='+id);
